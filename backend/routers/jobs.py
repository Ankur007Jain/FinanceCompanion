import asyncio
import json
import os
from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import StockAnalysis, MarketDataCache
from schemas import NightlyJobRequest, IngestAnalysisRequest, IngestSnapshotRequest
from services.nightly_runner import run_nightly_analysis
from services.stock_memory import maybe_update_stock_memory

router = APIRouter(prefix="/jobs", tags=["jobs"])


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
        "analyst_consensus": body.analyst_consensus,
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
    }

    # Synthesize events_json from earnings_date when the agent sends it but not events_json
    if not mapped.get("events_json") and body.earnings_date:
        mapped["events_json"] = json.dumps([{"date": body.earnings_date, "description": "Earnings"}])

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
        return {"status": "updated", "ticker": body.ticker}

    analysis = StockAnalysis(**{k: v for k, v in mapped.items() if v is not None or k in ("signal_convergence_score",)})
    db.add(analysis)
    db.commit()
    background_tasks.add_task(_run_memory_update, body.ticker, body.verdict or "", body.reasoning or "", body.news_summary or "", "")
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


@router.get("/admin/tickers")
def list_all_tickers(x_admin_secret: str = "", db: Session = Depends(get_db)):
    """Returns all unique tickers across all watchlists — used by the nightly agent."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    from models import WatchlistItem
    tickers = db.query(WatchlistItem.ticker).distinct().all()
    return {"tickers": [t[0] for t in tickers]}


@router.get("/admin/analyzed-today")
def analyzed_today(x_admin_secret: str = "", db: Session = Depends(get_db)):
    """Returns tickers already analyzed today — agent skips these to avoid redundant fetches."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    today = date.today()
    rows = db.query(StockAnalysis.ticker).filter(StockAnalysis.analysis_date == today).all()
    return {"date": str(today), "analyzed": [r[0] for r in rows]}


@router.get("/health")
def health():
    return {"status": "ok"}
