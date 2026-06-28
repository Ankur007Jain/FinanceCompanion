"""
Nightly Runner — orchestrates the multi-agent pipeline per ticker.
All data agents (Price, News, Event, Analyst) run in parallel.
Ripple and Verdict run after, in sequence.
Analysis is global per ticker — not per user.
"""
import asyncio
import json
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from agents.analyst_agent import fetch_analyst_data
from agents.event_agent import fetch_events
from agents.news_agent import fetch_news
from agents.price_agent import fetch_price_data
from agents.yf_fetcher import fetch_yf_data
from agents.ripple_agent import analyze_ripple
from agents.verdict_agent import generate_verdict
from models import StockAnalysis, WatchlistItem
from services.stock_memory import get_stock_memory, maybe_update_stock_memory

logger = logging.getLogger(__name__)


def _is_quiet_stock(
    price_change_pct: float | None,
    recent_analyses: list,
    events: list[dict],
) -> bool:
    """
    Returns True when a stock is quiet enough to skip LLM calls and reuse yesterday's analysis.
    Criteria (ALL must hold):
      - Price moved < 2% today
      - No upcoming event within 5 days
      - Same verdict for the last 3 consecutive days
      - Yesterday was not flagged as an important day
    """
    if price_change_pct is None or abs(price_change_pct) >= 2.0:
        return False

    today = date.today()
    for e in events:
        try:
            event_date = date.fromisoformat(str(e["date"]))
            if 0 < (event_date - today).days <= 5:
                return False
        except (ValueError, KeyError):
            pass

    if len(recent_analyses) < 3:
        return False

    verdicts = [a.verdict for a in recent_analyses[:3]]
    if len(set(verdicts)) > 1:
        return False

    if recent_analyses[0].is_important_day:
        return False

    return True


def _compute_signal_convergence(price, analyst, events: list[dict]) -> tuple[int, dict]:
    """Deterministically scores 7 independent low-hanging-fruit signals."""
    today = date.today()

    days_to_earnings = 999
    for e in events:
        desc = e.get("description", "").lower()
        if any(k in desc for k in ("earning", "eps", "quarterly result", "q1", "q2", "q3", "q4")):
            try:
                event_date = date.fromisoformat(str(e["date"]))
                days = (event_date - today).days
                if 0 < days < days_to_earnings:
                    days_to_earnings = days
            except (ValueError, KeyError):
                pass

    signals = {
        "oversold_rsi":         price.rsi is not None and price.rsi < 42,
        "near_52w_low":         price.range_position_pct is not None and price.range_position_pct < 35,
        "analyst_upside_15pct": analyst.upside_pct is not None and analyst.upside_pct > 15,
        "no_binary_risk":       days_to_earnings > 21,
        "positive_fcf":         analyst.free_cashflow is not None and analyst.free_cashflow > 0,
        "institutional_backing":analyst.inst_ownership_pct is not None and analyst.inst_ownership_pct > 0.40,
        "price_stabilizing":    (
            price.current_price is not None and price.ma_200 is not None
            and price.current_price > price.ma_200 * 0.90
        ),
    }
    return sum(signals.values()), signals


async def _analyze_single_ticker(ticker: str, is_leveraged: bool, sector: str, company_name: str, db: Session) -> None:
    today = date.today()

    # Skip if already ran today
    existing = db.query(StockAnalysis).filter(
        StockAnalysis.ticker == ticker,
        StockAnalysis.analysis_date == today,
    ).first()
    if existing:
        logger.info(f"[{ticker}] Already analyzed today — skipping.")
        return

    logger.info(f"[{ticker}] Fetching yfinance data...")

    try:
        loop = asyncio.get_event_loop()
        yf = await loop.run_in_executor(None, fetch_yf_data, ticker, db)
    except Exception as e:
        logger.error(f"[{ticker}] yfinance fetch failed: {e}")
        return

    logger.info(f"[{ticker}] Starting parallel data agents...")

    try:
        price, news, events, analyst = await asyncio.gather(
            fetch_price_data(ticker, yf_data=yf),
            fetch_news(ticker, company_name, yf_data=yf),
            fetch_events(ticker, prefetched=yf),
            fetch_analyst_data(ticker, prefetched=yf),
        )
        analyst.upside_pct = analyst.upside_pct  # recalc with real price
        if price.current_price:
            if analyst.target_mean:
                analyst.upside_pct = round(
                    (analyst.target_mean - price.current_price) / price.current_price * 100, 1
                )
    except Exception as e:
        logger.error(f"[{ticker}] Data agent failure: {e}")
        return

    # Smart skip — avoid Sonnet calls on quiet days (saves ~90% of LLM cost for those stocks)
    recent_all = (
        db.query(StockAnalysis)
        .filter(StockAnalysis.ticker == ticker)
        .order_by(StockAnalysis.analysis_date.desc())
        .limit(5)
        .all()
    )
    if _is_quiet_stock(price.day_change_pct, recent_all, events):
        logger.info(
            f"[{ticker}] Quiet day (Δ{price.day_change_pct:+.1f}%, "
            f"verdict stable={recent_all[0].verdict if recent_all else '?'}) — skipping LLM, reusing yesterday's analysis."
        )
        return

    logger.info(f"[{ticker}] Running Ripple agent...")
    try:
        ripple = await analyze_ripple(ticker, news, sector)
    except Exception as e:
        logger.error(f"[{ticker}] Ripple agent failed: {e}")
        ripple = "Ripple analysis unavailable."

    logger.info(f"[{ticker}] Running Verdict agent...")
    try:
        stock_mem = await get_stock_memory(ticker, db)
        recent_analyses = [
            {
                "date": str(r.analysis_date),
                "verdict": r.verdict,
                "current_price": r.current_price,
                "is_important_day": r.is_important_day,
                "importance_reason": r.importance_reason,
            }
            for r in recent_all
        ]
        # Find most recent BUY price to power the don't-panic check
        last_buy = next((r for r in recent_all if r.verdict == "BUY" and r.current_price), None)
        last_buy_price = last_buy.current_price if last_buy else None

        # Deterministic convergence score — computed before calling Claude
        conv_score, conv_details = _compute_signal_convergence(price, analyst, events)
        logger.info(f"[{ticker}] Signal convergence: {conv_score}/7 {conv_details}")

        verdict = await generate_verdict(
            ticker, price, news, events, analyst, ripple, stock_mem, is_leveraged,
            recent_analyses=recent_analyses,
            last_buy_price=last_buy_price,
            signal_convergence_score=conv_score,
            convergence_details=conv_details,
        )
    except Exception as e:
        logger.error(f"[{ticker}] Verdict agent failed: {e}")
        return

    # Persist analysis
    analysis = StockAnalysis(
        ticker=ticker,
        analysis_date=today,
        current_price=price.current_price,
        prev_close=price.prev_close,
        day_change_pct=price.day_change_pct,
        day_high=price.day_high,
        day_low=price.day_low,
        week_52_high=price.week_52_high,
        week_52_low=price.week_52_low,
        range_position_pct=price.range_position_pct,
        volume=price.volume,
        avg_volume=price.avg_volume,
        ma_50=price.ma_50,
        ma_200=price.ma_200,
        rsi=price.rsi,
        analyst_consensus=analyst.consensus,
        analyst_count=analyst.analyst_count,
        target_price_mean=analyst.target_mean,
        target_price_high=analyst.target_high,
        target_price_low=analyst.target_low,
        pe_trailing=analyst.pe_trailing,
        pe_forward=analyst.pe_forward,
        revenue_growth=analyst.revenue_growth,
        earnings_growth=analyst.earnings_growth,
        profit_margin=analyst.profit_margin,
        debt_to_equity=analyst.debt_to_equity,
        free_cashflow=analyst.free_cashflow,
        return_on_equity=analyst.return_on_equity,
        beta=analyst.beta,
        short_float_pct=analyst.short_float_pct,
        short_ratio=analyst.short_ratio,
        inst_ownership_pct=analyst.inst_ownership_pct,
        insider_ownership_pct=analyst.insider_ownership_pct,
        sp500_52w_change=analyst.sp500_52w_change,
        stock_52w_change=analyst.stock_52w_change,
        dividend_yield=analyst.dividend_yield,
        market_cap=analyst.market_cap,
        sector=analyst.sector,
        industry=analyst.industry,
        fundamentals_json=analyst.fundamentals_json,
        verdict=verdict.verdict,
        entry_target=verdict.entry_target,
        exit_target=verdict.exit_target,
        stop_loss=verdict.stop_loss,
        hold_period=verdict.hold_period,
        reasoning=verdict.reasoning,
        conviction_score=verdict.conviction_score,
        risk_level=verdict.risk_level,
        confidence=verdict.confidence,
        bull_case=verdict.bull_case,
        bear_case=verdict.bear_case,
        thesis_invalidation=verdict.thesis_invalidation,
        news_summary=news,
        events_json=json.dumps(events),
        ripple_analysis=ripple,
        data_conflicts="; ".join(filter(None, [price.conflict_notes, analyst.conflict_notes, verdict.conflict_flags])),
        is_important_day=verdict.is_important_day,
        importance_reason=verdict.importance_reason,
        entry_quality=verdict.entry_quality,
        hold_and_forget_rating=verdict.hold_and_forget_rating,
        position_size_pct=verdict.position_size_pct,
        scenario_bull=verdict.scenario_bull,
        scenario_base=verdict.scenario_base,
        scenario_bear=verdict.scenario_bear,
        scenario_bull_pct=verdict.scenario_bull_pct,
        scenario_base_pct=verdict.scenario_base_pct,
        scenario_bear_pct=verdict.scenario_bear_pct,
        scenario_bull_prob=verdict.scenario_bull_prob,
        scenario_base_prob=verdict.scenario_base_prob,
        scenario_bear_prob=verdict.scenario_bear_prob,
        dont_panic_note=verdict.dont_panic_note,
        signal_convergence_score=conv_score,
        convergence_details=json.dumps(conv_details),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    logger.info(f"[{ticker}] Analysis saved. Verdict: {verdict.verdict}")

    await maybe_update_stock_memory(ticker, verdict.verdict, verdict.reasoning, news, json.dumps(events), db)


async def run_nightly_analysis(db: Session, tickers: list[str] | None = None) -> dict:
    if tickers is None:
        rows = db.query(
            WatchlistItem.ticker,
            WatchlistItem.is_leveraged,
            WatchlistItem.sector,
            WatchlistItem.company_name,
        ).distinct(WatchlistItem.ticker).all()
    else:
        rows = db.query(
            WatchlistItem.ticker,
            WatchlistItem.is_leveraged,
            WatchlistItem.sector,
            WatchlistItem.company_name,
        ).filter(WatchlistItem.ticker.in_(tickers)).distinct(WatchlistItem.ticker).all()

    if not rows:
        return {"status": "no_tickers", "processed": 0}

    logger.info(f"Nightly run starting for {len(rows)} ticker(s)...")
    tasks = [
        _analyze_single_ticker(r.ticker, r.is_leveraged or False, r.sector or "", r.company_name or r.ticker, db)
        for r in rows
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [str(r) for r in results if isinstance(r, Exception)]

    return {
        "status": "complete",
        "processed": len(rows),
        "errors": errors,
    }
