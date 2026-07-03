import asyncio
import json
import os
from datetime import date, datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
import anthropic

from database import get_db
from models import StockAnalysis, WatchlistItem, MarketDataCache, StockReport
from routers.auth import get_current_user
from schemas import DigestItem, StockAnalysisOut, ImportantFlag, ReportDayOut, StockReportOut
from services.stock_memory import update_memory_from_report

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _change_summary(cur: StockAnalysis, prev: StockAnalysis) -> tuple[bool, str]:
    """Return (has_meaningful_change, human-readable summary string)."""
    parts: list[str] = []

    if cur.verdict != prev.verdict:
        parts.append(f"{prev.verdict or '?'} → {cur.verdict or '?'}")

    if cur.is_important_day:
        parts.append("Important day")

    c_conv = cur.conviction_score or 0
    p_conv = prev.conviction_score or 0
    if abs(c_conv - p_conv) >= 10:
        parts.append(f"Conviction {p_conv}→{c_conv}")

    c_rsi = cur.rsi or 0
    p_rsi = prev.rsi or 0
    if abs(c_rsi - p_rsi) >= 5:
        parts.append(f"RSI {p_rsi:.0f}→{c_rsi:.0f}")

    if cur.news_summary and cur.news_summary != (prev.news_summary or ""):
        parts.append("New news")

    if cur.data_conflicts and cur.data_conflicts != (prev.data_conflicts or ""):
        parts.append("Data conflict flagged")

    c_sig = cur.signal_convergence_score or 0
    p_sig = prev.signal_convergence_score or 0
    if abs(c_sig - p_sig) >= 2:
        parts.append(f"Signals {p_sig}→{c_sig}/10")

    return bool(parts), " · ".join(parts[:4])


@router.get("/digest", response_model=list[DigestItem])
def get_digest(id_token: str, db: Session = Depends(get_db)):
    """Digest for all stocks in the user's watchlist — most recent analysis within 7 days."""
    user = get_current_user(id_token, db)
    watchlist = db.query(WatchlistItem).filter(WatchlistItem.user_email == user.email).all()
    cutoff = date.today() - timedelta(days=7)
    result = []
    for item in watchlist:
        analysis = (
            db.query(StockAnalysis)
            .filter(
                StockAnalysis.ticker == item.ticker,
                StockAnalysis.analysis_date >= cutoff,
            )
            .order_by(StockAnalysis.analysis_date.desc())
            .first()
        )

        has_unread = False
        change_summary = None
        days_since_read = None

        if analysis:
            if item.last_read_analysis_id is None:
                # Never read — flag as unread with no delta (first time seeing any analysis)
                has_unread = True
                change_summary = "New analysis available"
            elif item.last_read_analysis_id != analysis.id:
                # Read before, but a newer analysis exists — compute delta
                prev = db.query(StockAnalysis).filter(
                    StockAnalysis.id == item.last_read_analysis_id
                ).first()
                if prev:
                    has_meaningful, summary = _change_summary(analysis, prev)
                    has_unread = has_meaningful
                    change_summary = summary if has_meaningful else None
                else:
                    has_unread = True
                    change_summary = "New analysis available"

            if has_unread and item.last_read_at:
                days_since_read = (datetime.utcnow() - item.last_read_at).days

        close_5d = None
        if analysis:
            cache = (
                db.query(MarketDataCache)
                .filter(MarketDataCache.ticker == item.ticker)
                .order_by(MarketDataCache.cache_date.desc())
                .first()
            )
            if cache and cache.history_json:
                try:
                    hist = json.loads(cache.history_json)
                    closes = [day["Close"] for day in hist if day.get("Close") is not None]
                    close_5d = [round(c, 2) for c in closes[-7:]] if len(closes) >= 2 else None
                except Exception:
                    pass

        result.append(DigestItem(
            ticker=item.ticker,
            company_name=item.company_name,
            is_leveraged=item.is_leveraged or False,
            shares=item.shares,
            avg_cost=item.avg_cost,
            analysis=StockAnalysisOut.model_validate(analysis) if analysis else None,
            has_unread=has_unread,
            change_summary=change_summary,
            days_since_read=days_since_read,
            close_5d=close_5d,
        ))
    return result


@router.get("/reports", response_model=list[ReportDayOut])
def get_reports(id_token: str, limit: int = 7, db: Session = Depends(get_db)):
    """Last N nightly report summaries for the user's watchlist, newest first."""
    user = get_current_user(id_token, db)
    watchlist_tickers = [
        row.ticker
        for row in db.query(WatchlistItem).filter(WatchlistItem.user_email == user.email).all()
    ]
    if not watchlist_tickers:
        return []

    dates = (
        db.query(StockAnalysis.analysis_date)
        .filter(StockAnalysis.ticker.in_(watchlist_tickers))
        .distinct()
        .order_by(StockAnalysis.analysis_date.desc())
        .limit(limit)
        .all()
    )

    result = []
    for (report_date,) in dates:
        analyses = (
            db.query(StockAnalysis)
            .filter(
                StockAnalysis.ticker.in_(watchlist_tickers),
                StockAnalysis.analysis_date == report_date,
            )
            .all()
        )
        by_verdict: dict[str, list[str]] = {}
        important_flags: list[ImportantFlag] = []
        for a in analyses:
            by_verdict.setdefault(a.verdict, []).append(a.ticker)
            if a.is_important_day:
                important_flags.append(ImportantFlag(
                    ticker=a.ticker,
                    verdict=a.verdict,
                    importance_reason=a.importance_reason,
                ))
        result.append(ReportDayOut(
            report_date=str(report_date),
            analyzed_count=len(analyses),
            total_watchlist=len(watchlist_tickers),
            by_verdict=by_verdict,
            important_flags=important_flags,
        ))
    return result


@router.get("/{ticker}/latest", response_model=StockAnalysisOut)
def get_latest(ticker: str, id_token: str, db: Session = Depends(get_db)):
    get_current_user(id_token, db)
    analysis = db.query(StockAnalysis).filter(
        StockAnalysis.ticker == ticker.upper(),
    ).order_by(StockAnalysis.analysis_date.desc()).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this ticker.")
    return analysis


@router.get("/important", response_model=list[StockAnalysisOut])
def get_important(id_token: str, days: int = 30, db: Session = Depends(get_db)):
    """Important-day analyses across the user's watchlist (verdict reversals, earnings, catalysts)."""
    user = get_current_user(id_token, db)
    tickers = [
        row.ticker
        for row in db.query(WatchlistItem).filter(WatchlistItem.user_email == user.email).all()
    ]
    if not tickers:
        return []
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=days)
    return (
        db.query(StockAnalysis)
        .filter(
            StockAnalysis.ticker.in_(tickers),
            StockAnalysis.is_important_day == True,  # noqa: E712
            StockAnalysis.analysis_date >= cutoff,
        )
        .order_by(StockAnalysis.analysis_date.desc())
        .limit(50)
        .all()
    )


@router.get("/{ticker}/history", response_model=list[StockAnalysisOut])
def get_history(ticker: str, id_token: str, days: int = 30, db: Session = Depends(get_db)):
    get_current_user(id_token, db)
    rows = (
        db.query(StockAnalysis)
        .filter(StockAnalysis.ticker == ticker.upper())
        .order_by(StockAnalysis.analysis_date.desc())
        .limit(days)
        .all()
    )
    return rows


@router.get("/{ticker}/report", response_model=StockReportOut | None)
def get_report(ticker: str, id_token: str, db: Session = Depends(get_db)):
    get_current_user(id_token, db)
    report = (
        db.query(StockReport)
        .filter(StockReport.ticker == ticker.upper())
        .order_by(StockReport.report_date.desc())
        .first()
    )
    return report


_REPORT_SYSTEM = """You are a financial analyst writing a plain-English debrief for a busy professional.
You have access to the last 30 days of AI-generated daily analyses for a specific stock.
Each analysis includes: verdict (BUY/HOLD/SELL/WATCH), price, conviction score (0-100), reasoning,
bull case, bear case, entry target, exit target, stop loss, and scenario probabilities.

Write a concise analytical report in markdown. Be specific with numbers and dates. No jargon.
Write like a smart friend who tracked this stock for a month and is catching you up.
Use only: ## headers, **bold**, bullet points, and plain text. Never use strikethrough (~~)."""

_REPORT_PROMPT = """Here are the past {n} daily analyses for {ticker}, newest first:

{analyses}

Write a report covering these sections (use ## headers):

## Verdict Trajectory
How did the verdict move over this period and why? Note any flips and what drove them.

## Conviction Trend
Was confidence building or declining? Highlight the highest and lowest conviction days.

## Price Target Accuracy
Compare past entry/exit targets to what actually happened with the price. Were the calls useful?

## Recurring Themes
What macro factors, catalysts, or risks kept showing up across multiple days?

## What the AI Got Right vs Wrong
Honest assessment — where was the analysis accurate, where did it miss?

## Watch For
One or two things to monitor going forward based on the pattern you've seen.

Keep the whole report under 600 words. Be specific, not generic."""


@router.post("/{ticker}/report", response_model=StockReportOut)
def generate_report(ticker: str, id_token: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    get_current_user(id_token, db)
    ticker = ticker.upper()
    today = date.today()

    # Return cached report if already generated today
    existing = db.query(StockReport).filter(
        StockReport.ticker == ticker, StockReport.report_date == today
    ).first()
    if existing:
        return existing

    # Fetch last 30 analyses
    analyses = (
        db.query(StockAnalysis)
        .filter(StockAnalysis.ticker == ticker)
        .order_by(StockAnalysis.analysis_date.desc())
        .limit(30)
        .all()
    )
    if not analyses:
        raise HTTPException(status_code=404, detail="No analyses found for this ticker.")

    # Build compact text representation of each analysis
    def _fmt_analysis(a: StockAnalysis) -> str:
        lines = [f"Date: {a.analysis_date}  |  Verdict: {a.verdict}  |  Price: ${a.current_price or 'N/A'}  |  Conviction: {a.conviction_score or 'N/A'}/100"]
        if a.reasoning:       lines.append(f"Reasoning: {a.reasoning}")
        if a.bull_case:       lines.append(f"Bull: {a.bull_case}")
        if a.bear_case:       lines.append(f"Bear: {a.bear_case}")
        if a.entry_target:    lines.append(f"Entry target: ${a.entry_target}  Exit: ${a.exit_target}  Stop: ${a.stop_loss}")
        if a.scenario_bull_prob is not None:
            lines.append(f"Scenarios: bull {a.scenario_bull_prob}% / base {a.scenario_base_prob}% / bear {a.scenario_bear_prob}%")
        return "\n".join(lines)

    analyses_text = "\n\n---\n\n".join(_fmt_analysis(a) for a in analyses)
    prompt = _REPORT_PROMPT.format(ticker=ticker, n=len(analyses), analyses=analyses_text)

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI not configured.")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=_REPORT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    import re
    content = re.sub(r"~~(.+?)~~", r"\1", resp.content[0].text.strip())

    report = StockReport(
        ticker=ticker,
        report_date=today,
        content=content,
        analyses_count=len(analyses),
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Option B: extract lessons from report → append to StockMemory (background, non-blocking)
    def _run_memory_update():
        asyncio.run(update_memory_from_report(ticker, content, db))
    background_tasks.add_task(_run_memory_update)

    return report
