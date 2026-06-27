import json
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import StockAnalysis, WatchlistItem, MarketDataCache
from routers.auth import get_current_user
from schemas import DigestItem, StockAnalysisOut, ImportantFlag, ReportDayOut

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
