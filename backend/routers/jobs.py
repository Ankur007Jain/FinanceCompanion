import asyncio
import json
import os
from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import StockAnalysis, MarketDataCache
from schemas import NightlyJobRequest, IngestAnalysisRequest, IngestSnapshotRequest, IngestCorrelationsRequest
from services.nightly_runner import run_nightly_analysis
from services.stock_memory import maybe_update_stock_memory

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Gemini 2.5 Flash, thinking disabled (thinking_budget=0) — verify against
# https://ai.google.dev/gemini-api/docs/pricing before relying on this for real budgeting.
_GEMINI_FLASH_PRICE_IN = 0.30   # per 1M input tokens
_GEMINI_FLASH_PRICE_OUT = 2.50  # per 1M output tokens


@router.post("/nightly")
async def trigger_nightly(body: NightlyJobRequest, background_tasks: BackgroundTasks):
    if body.secret != os.getenv("JOB_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid job secret.")

    async def _run():
        session = SessionLocal()
        try:
            result = await run_nightly_analysis(session, body.tickers)
            return result
        finally:
            session.close()

    background_tasks.add_task(_run)
    return {"status": "started", "tickers": body.tickers or "all"}


def _run_memory_update(ticker: str, verdict: str, reasoning: str, news_summary: str, events_json: str):
    session = SessionLocal()
    try:
        asyncio.run(maybe_update_stock_memory(ticker, verdict, reasoning, news_summary, events_json, session))
    finally:
        session.close()


def _check_target_sanity(verdict, current_price, entry_target, exit_target, stop_loss) -> list[str]:
    """Flags nonsensical target combinations — a stop above current price on a BUY, an exit
    below entry, an entry wildly far from the actual price. Doesn't block ingest (a missing
    ticker is worse than an imperfect one); just surfaces a warning into data_conflicts so
    both the chat AI and the report treat the analysis with the same caution as a real
    cross-source data conflict. Catches a specific hallucination class: a plausible-looking
    number that doesn't actually cohere with the rest of the verdict."""
    issues = []
    if current_price is None:
        return issues
    if verdict == "BUY":
        if stop_loss is not None and stop_loss >= current_price:
            issues.append(f"stop_loss ${stop_loss} is at/above current price ${current_price} for a BUY")
        if entry_target is not None and exit_target is not None and exit_target <= entry_target:
            issues.append(f"exit_target ${exit_target} is not above entry_target ${entry_target} for a BUY")
        if entry_target is not None and abs(entry_target - current_price) / current_price > 0.3:
            issues.append(f"entry_target ${entry_target} is >30% from current price ${current_price}")
    elif verdict == "SELL":
        if stop_loss is not None and stop_loss <= current_price:
            issues.append(f"stop_loss ${stop_loss} is at/below current price ${current_price} for a SELL")
        if entry_target is not None and exit_target is not None and exit_target >= entry_target:
            issues.append(f"exit_target ${exit_target} is not below entry_target ${entry_target} for a SELL")
    return issues


def _run_simple_fields(analysis_id: str):
    """Pre-generate plain-English fields after ingest — without this, the UI's default
    Simple mode falls back to a live translation on every card expand, for every user."""
    from services.simple_fields import generate_simple_fields
    session = SessionLocal()
    try:
        analysis = session.get(StockAnalysis, analysis_id)
        if analysis and not analysis.reasoning_simple:
            asyncio.run(generate_simple_fields(analysis, session))
    finally:
        session.close()


@router.post("/ingest-analysis")
def ingest_analysis(body: IngestAnalysisRequest, background_tasks: BackgroundTasks, x_job_secret: str = "", db: Session = Depends(get_db)):
    """Called by the GitHub Actions nightly agent to persist analysis results."""
    if x_job_secret != os.getenv("JOB_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid job secret.")

    # Map schema field names → model column names
    mapped = {
        "ticker": body.ticker,
        "analysis_date": body.analysis_date,
        "current_price": body.current_price,
        "day_change_pct": body.price_change_pct,
        "week_52_high": body.week52_high,
        "week_52_low": body.week52_low,
        "range_position_pct": body.week52_position_pct,
        "ma_50": body.ma50,
        "ma_200": body.ma200,
        "rsi": body.rsi,
        "support_20d": body.support_20d,
        "resistance_20d": body.resistance_20d,
        "pivot_point": body.pivot_point,
        "pivot_r1": body.pivot_r1,
        "pivot_s1": body.pivot_s1,
        "sp500_day_chg": body.sp500_day_chg,
        "sector_etf": body.sector_etf,
        "sector_day_chg": body.sector_day_chg,
        "relative_strength_1d": body.relative_strength_1d,
        "fh_price": body.fh_price,
        "fh_analyst_consensus": body.fh_analyst_consensus,
        "data_conflicts": body.data_conflicts,
        "analyst_consensus": body.analyst_consensus,
        "analyst_count": body.analyst_count,
        "target_price_mean": body.target_price_mean,
        "target_price_high": body.target_price_high,
        "target_price_low": body.target_price_low,
        "pe_trailing": body.pe_trailing,
        "pe_forward": body.pe_forward,
        "revenue_growth": body.revenue_growth,
        "earnings_growth": body.earnings_growth,
        "profit_margin": body.profit_margin,
        "debt_to_equity": body.debt_to_equity,
        "free_cashflow": body.free_cashflow,
        "return_on_equity": body.return_on_equity,
        "beta": body.beta,
        "short_float_pct": body.short_float_pct,
        "short_ratio": body.short_ratio,
        "inst_ownership_pct": body.inst_ownership_pct,
        "insider_ownership_pct": body.insider_ownership_pct,
        "sp500_52w_change": body.sp500_52w_change,
        "stock_52w_change": body.stock_52w_change,
        "sp500_5y_change": body.sp500_5y_change,
        "stock_5y_change": body.stock_5y_change,
        "dividend_yield": body.dividend_yield,
        "market_cap": body.market_cap,
        "sector": body.sector,
        "industry": body.industry,
        "verdict": body.verdict,
        "entry_target": body.entry_target,
        "exit_target": body.exit_target,
        "stop_loss": body.stop_loss,
        "hold_period": body.hold_period,
        "reasoning": body.reasoning,
        "conviction_score": body.conviction_score,
        "risk_level": body.risk_level,
        "confidence": body.confidence,
        "bull_case": body.bull_case,
        "bear_case": body.bear_case,
        "thesis_invalidation": body.thesis_invalidation,
        "news_summary": body.news_summary,
        "ripple_analysis": body.ripple_analysis,
        "is_important_day": body.is_important_day,
        "importance_reason": body.importance_reason,
        "entry_quality": body.entry_quality,
        "hold_and_forget_rating": body.hold_and_forget_rating,
        "position_size_pct": body.position_size_pct,
        "scenario_bull": body.scenario_bull,
        "scenario_base": body.scenario_base,
        "scenario_bear": body.scenario_bear,
        "scenario_bull_pct": body.scenario_bull_pct,
        "scenario_base_pct": body.scenario_base_pct,
        "scenario_bear_pct": body.scenario_bear_pct,
        "scenario_bull_prob": body.scenario_bull_prob,
        "scenario_base_prob": body.scenario_base_prob,
        "scenario_bear_prob": body.scenario_bear_prob,
        "dont_panic_note": body.dont_panic_note,
        "signal_convergence_score": body.signal_convergence_score,
        "convergence_details": body.convergence_details,
        "verdict_a": body.verdict_a,
        "verdict_b": body.verdict_b,
        "verdict_agreement": body.verdict_agreement,
        "split_reason": body.split_reason,
        # Gemini Verdict B is the only nightly step that's a scripted API call with a real
        # usage object — Claude's steps run as the orchestrating agent's own reasoning.
        "tokens_input": body.gemini_tokens_input,
        "tokens_output": body.gemini_tokens_output,
        "cost_usd": (
            (body.gemini_tokens_input / 1_000_000) * _GEMINI_FLASH_PRICE_IN
            + (body.gemini_tokens_output / 1_000_000) * _GEMINI_FLASH_PRICE_OUT
        ) if body.gemini_tokens_input is not None and body.gemini_tokens_output is not None else None,
    }

    # Synthesize events_json from earnings_date when the agent sends it but not events_json
    if not mapped.get("events_json") and body.earnings_date:
        mapped["events_json"] = json.dumps([{"date": body.earnings_date, "description": "Earnings"}])

    target_issues = _check_target_sanity(
        body.verdict, body.current_price, body.entry_target, body.exit_target, body.stop_loss
    )
    if target_issues:
        warning = "Target sanity: " + "; ".join(target_issues)
        mapped["data_conflicts"] = f"{mapped['data_conflicts']}; {warning}" if mapped.get("data_conflicts") else warning

    existing = db.query(StockAnalysis).filter(
        StockAnalysis.ticker == body.ticker,
        StockAnalysis.analysis_date == body.analysis_date,
    ).first()

    if existing:
        for col, value in mapped.items():
            if value is not None:
                setattr(existing, col, value)
        db.commit()
        background_tasks.add_task(_run_memory_update, body.ticker, body.verdict or "", body.reasoning or "", body.news_summary or "", "")
        background_tasks.add_task(_run_simple_fields, existing.id)
        return {"status": "updated", "ticker": body.ticker}

    analysis = StockAnalysis(**{k: v for k, v in mapped.items() if v is not None or k in ("signal_convergence_score",)})
    db.add(analysis)
    db.commit()
    background_tasks.add_task(_run_memory_update, body.ticker, body.verdict or "", body.reasoning or "", body.news_summary or "", "")
    background_tasks.add_task(_run_simple_fields, analysis.id)
    return {"status": "created", "ticker": body.ticker}


@router.post("/ingest-snapshot")
def ingest_snapshot(body: IngestSnapshotRequest, x_job_secret: str = "", db: Session = Depends(get_db)):
    """Called by GHA after raw data fetch — persists raw market data before verdict agents run."""
    if x_job_secret != os.getenv("JOB_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid job secret.")

    entry = MarketDataCache(
        ticker=body.ticker,
        cache_date=body.cache_date,
        info_json=body.info_json,
        history_json=body.history_json,
        news_json=body.news_json,
        calendar_json=body.calendar_json,
    )
    db.merge(entry)
    db.commit()
    return {"status": "saved", "ticker": body.ticker, "date": str(body.cache_date)}


@router.post("/ingest-correlations")
def ingest_correlations(body: IngestCorrelationsRequest, x_job_secret: str = "", db: Session = Depends(get_db)):
    """Called by scripts/compute_correlations.py after the daily correlation run.
    Replaces the WHOLE table with today's fresh pairs — a full recompute each day,
    not an incremental update, so there's never a stale pair left over from a ticker
    that dropped out of every watchlist.

    Real production bug this guards against: TickerCorrelation's primary key is
    (ticker_a, ticker_b) only, NOT (ticker_a, ticker_b, computed_date) - a pair can
    only ever have ONE row, always the latest. The old code deleted only rows
    matching TODAY's computed_date before inserting, which matches nothing on any
    normal day (nothing has today's date yet) - so yesterday's row for every pair
    was still there when the fresh insert ran, and it collided on the very first
    pair (psycopg2.errors.UniqueViolation, confirmed in prod: every single run
    failed from 2026-07-17 onward, the day after the table's first successful
    populate). Deleting unconditionally is correct and safe here specifically
    because every run recomputes the COMPLETE current universe of pairs - there's
    no partial-payload case where wiping the table first would lose data the
    incoming payload doesn't replace."""
    if x_job_secret != os.getenv("JOB_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid job secret.")
    from models import TickerCorrelation

    db.query(TickerCorrelation).delete()
    for p in body.pairs:
        db.add(TickerCorrelation(
            ticker_a=p.ticker_a, ticker_b=p.ticker_b,
            corr_30d=p.corr_30d, corr_90d=p.corr_90d, corr_180d=p.corr_180d,
            p_value_90d=p.p_value_90d, significant=p.significant,
            computed_date=body.computed_date,
        ))
    db.commit()
    return {"status": "saved", "pairs": len(body.pairs), "date": str(body.computed_date)}


@router.get("/admin/tickers")
def list_all_tickers(x_admin_secret: str = "", db: Session = Depends(get_db)):
    """Returns all unique tickers across all watchlists — used by the nightly agent.
    Excludes tickers an admin has disabled analysis for."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    from models import TickerControl, WatchlistItem
    tickers = {t[0] for t in db.query(WatchlistItem.ticker).distinct().all()}
    disabled = {c.ticker for c in db.query(TickerControl).filter(TickerControl.analysis_enabled.is_(False)).all()}
    return {"tickers": sorted(tickers - disabled)}


@router.get("/admin/closes")
def get_closes(x_admin_secret: str = "", days: int = 300, db: Session = Depends(get_db)):
    """Daily closing prices for every tracked ticker — feeds the correlation-matrix
    compute script. Extracts just {date: close} from each ticker's latest
    market_data_cache.history_json rather than returning the full OHLCV blob (which
    also carries Open/High/Low/Volume/Dividends/Splits for every ticker — history_json
    alone runs ~150-250KB per ticker, and none of that is needed here).

    history_json has shipped in two shapes depending on which nightly pipeline wrote
    it: a list of {"Date": ..., "Close": ..., ...} records (production GHA path,
    orient="records"), or a {"columns": [...], "data": [...], "index": [...]} dict
    (secondary /jobs/nightly path, orient="split"). Both are handled.
    """
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    from models import TickerControl, WatchlistItem
    from datetime import timedelta

    tickers = {t[0] for t in db.query(WatchlistItem.ticker).distinct().all()}
    disabled = {c.ticker for c in db.query(TickerControl).filter(TickerControl.analysis_enabled.is_(False)).all()}
    tickers -= disabled
    cutoff = date.today() - timedelta(days=days)

    result: dict[str, dict[str, float]] = {}
    for ticker in sorted(tickers):
        cache = (
            db.query(MarketDataCache)
            .filter(MarketDataCache.ticker == ticker)
            .order_by(MarketDataCache.cache_date.desc())
            .first()
        )
        if not cache or not cache.history_json:
            continue
        try:
            raw = json.loads(cache.history_json)
        except Exception:
            continue

        closes: dict[str, float] = {}
        try:
            if isinstance(raw, list):  # orient="records"
                for row in raw:
                    d = str(row.get("Date", ""))[:10]
                    c = row.get("Close")
                    if d and c is not None and d >= cutoff.isoformat():
                        closes[d] = float(c)
            elif isinstance(raw, dict) and "columns" in raw:  # orient="split"
                cols = raw["columns"]
                ci = cols.index("Close")
                for idx, row in zip(raw.get("index", []), raw.get("data", [])):
                    d = str(idx)[:10]
                    c = row[ci]
                    if d and c is not None and d >= cutoff.isoformat():
                        closes[d] = float(c)
        except Exception:
            continue

        if closes:
            result[ticker] = closes

    return {"closes": result}


@router.get("/admin/memories")
def get_stock_memories(x_admin_secret: str = "", tickers: str = "", db: Session = Depends(get_db)):
    """Returns per-ticker memory narratives — the nightly verdict agents read these so
    lessons extracted from past reports (e.g. 'stale analyst targets') actually inform
    the next night's verdict instead of only being visible to the chat assistant."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    from models import StockMemory
    q = db.query(StockMemory)
    if tickers:
        q = q.filter(StockMemory.ticker.in_([t.strip().upper() for t in tickers.split(",") if t.strip()]))
    return {"memories": {m.ticker: m.memory_narrative for m in q.all() if m.memory_narrative}}


@router.get("/admin/verdict-history")
def verdict_history(x_admin_secret: str = "", days: int = 45, db: Session = Depends(get_db)):
    """Feeds the weekly Verdict Scorecard agent — every verdict with its targets so
    outcomes can be replayed against actual subsequent prices."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=days)
    rows = (
        db.query(StockAnalysis)
        .filter(StockAnalysis.analysis_date >= cutoff, StockAnalysis.verdict.isnot(None))
        .order_by(StockAnalysis.analysis_date)
        .all()
    )
    return {"analyses": [
        {
            "ticker": r.ticker,
            "date": r.analysis_date.isoformat(),
            "verdict": r.verdict,
            "conviction": r.conviction_score,
            "price": r.current_price,
            "entry_target": r.entry_target,
            "exit_target": r.exit_target,
            "stop_loss": r.stop_loss,
            "hold_period": r.hold_period,
        }
        for r in rows
    ]}


# Columns whose sudden NULL-spike means a pipeline regression (each went silently
# missing at least once before this sentinel existed).
_DQ_COLUMNS = [
    "current_price", "rsi", "ma_50", "ma_200", "conviction_score", "reasoning",
    "pe_trailing", "revenue_growth", "free_cashflow", "inst_ownership_pct",
    "stock_52w_change", "stock_5y_change", "target_price_mean",
    "reasoning_simple", "verdict_b", "tokens_input",
]


@router.get("/admin/data-quality")
def data_quality(x_admin_secret: str = "", days: int = 7, db: Session = Depends(get_db)):
    """Feeds the daily Data Quality Sentinel — per-date NULL rates for key columns
    (a column that was populated yesterday and NULL today = silent pipeline break)
    plus tickers missing from the latest run."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    from datetime import timedelta
    from models import TickerControl, WatchlistItem
    cutoff = date.today() - timedelta(days=days)

    rows = db.query(StockAnalysis).filter(StockAnalysis.analysis_date >= cutoff).all()
    by_date: dict[str, list[StockAnalysis]] = {}
    for r in rows:
        by_date.setdefault(r.analysis_date.isoformat(), []).append(r)

    null_rates = {
        d: {
            "rows": len(drows),
            "null_pct": {
                col: round(100 * sum(1 for r in drows if getattr(r, col) is None) / len(drows), 1)
                for col in _DQ_COLUMNS
            },
        }
        for d, drows in sorted(by_date.items())
    }

    expected = {t[0] for t in db.query(WatchlistItem.ticker).distinct().all()}
    disabled = {c.ticker for c in db.query(TickerControl).filter(TickerControl.analysis_enabled.is_(False)).all()}
    expected -= disabled
    latest_date = max(by_date) if by_date else None
    analyzed_latest = {r.ticker for r in by_date.get(latest_date, [])}
    return {
        "null_rates_by_date": null_rates,
        "latest_date": latest_date,
        "expected_tickers": len(expected),
        "missing_in_latest": sorted(expected - analyzed_latest),
    }


@router.post("/admin/memories/{ticker}/lesson")
def append_memory_lesson(ticker: str, body: dict, x_admin_secret: str = "", db: Session = Depends(get_db)):
    """Scorecard agent feeds systematic verdict failures back into stock memory so
    the nightly verdict agents see them — closing the outcome loop, not just the
    reasoning loop."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    lesson = (body.get("lesson") or "").strip()
    if not lesson:
        raise HTTPException(status_code=422, detail="lesson is required.")
    from services.stock_memory import append_lesson
    ticker = ticker.upper()
    mem = append_lesson(ticker, lesson, "Scorecard", db)
    return {"ticker": ticker, "memory_chars": len(mem.memory_narrative)}


@router.post("/admin/user-learnings")
def seed_user_learning(body: dict, x_admin_secret: str = "", db: Session = Depends(get_db)):
    """Test-seeding utility, not a real product flow — UserLearning rows are normally
    created only via the chat save_learning tool. Lets e2e tests create real rows
    through the API (matching ingest-analysis/ingest-snapshot) instead of writing to
    the DB directly."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    from models import UserLearning
    email = (body.get("user_email") or "").strip()
    learning = (body.get("learning") or "").strip()
    if not email or not learning:
        raise HTTPException(status_code=422, detail="user_email and learning are required.")
    row = UserLearning(user_email=email, learning=learning, ticker=(body.get("ticker") or "").strip().upper() or None)
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.get("/admin/analyzed-today")
def analyzed_today(x_admin_secret: str = "", db: Session = Depends(get_db)):
    """Returns tickers already analyzed today — agent skips these to avoid redundant fetches."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    today = date.today()
    rows = db.query(StockAnalysis.ticker).filter(StockAnalysis.analysis_date == today).all()
    return {"date": str(today), "analyzed": [r[0] for r in rows]}


@router.post("/admin/backfill-simple")
async def backfill_simple_fields(x_admin_secret: str = "", db: Session = Depends(get_db)):
    """One-time backfill: generate simple fields for all analyses that are missing them."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    from services.simple_fields import generate_simple_fields
    rows = db.query(StockAnalysis).filter(StockAnalysis.reasoning_simple.is_(None)).all()
    count = len(rows)
    for row in rows:
        await generate_simple_fields(row, db)
    return {"backfilled": count}


@router.post("/admin/set-user-tier")
def set_user_tier(email: str, is_admin: bool = False, tier: str = "free", x_admin_secret: str = "", db: Session = Depends(get_db)):
    """Exempts a user from the free-tier chat token cap — this is an internal app-level
    counter (users.tokens_used), unrelated to Anthropic API billing/credits."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    from models import User
    user = db.get(User, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_admin = is_admin
    user.tier = tier
    db.commit()
    return {"email": email, "is_admin": user.is_admin, "tier": user.tier, "tokens_used": user.tokens_used}


@router.get("/health")
def health():
    return {"status": "ok"}
