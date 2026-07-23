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
from services.simple_fields import generate_simple_fields

logger = logging.getLogger(__name__)

# Pricing per million tokens. cache_write is the 5-minute-TTL rate (1.25x base
# input), matching what we actually use — see prompt_builder.py/streaming.py, no
# 1h-TTL cache_control anywhere in this codebase.
# Real bugs fixed here alongside the Sonnet 5 rollout: (1) claude-haiku-4-5-20251001's
# rates were stale/wrong ($0.80/$4.00/$0.08 vs the real published $1/$5/$0.10 -
# understated Haiku cost by 20% in every nightly cost_usd figure), and (2) cache_write
# tokens were tracked in the returned tuple but never actually priced into `cost` at
# all - every cache write this app has ever paid for was invisible to cost_usd.
_PRICING = {
    "claude-sonnet-5":           {"in": 2.0,  "out": 10.0, "cache_read": 0.20, "cache_write": 2.50},
    "claude-sonnet-4-6":         {"in": 3.0,  "out": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-haiku-4-5-20251001": {"in": 1.0,  "out": 5.0,  "cache_read": 0.10, "cache_write": 1.25},
}


def _sum_usages(usages: list[dict]) -> tuple[int, int, int, int, float]:
    """Returns (tokens_input, tokens_output, cache_read, cache_write, cost_usd)."""
    tin = tout = tcr = tcw = 0
    cost = 0.0
    for u in usages:
        p = _PRICING.get(u.get("model", "claude-sonnet-5"), _PRICING["claude-sonnet-5"])
        inp = u.get("input_tokens", 0) or 0
        out = u.get("output_tokens", 0) or 0
        cr  = u.get("cache_read", 0) or 0
        cw  = u.get("cache_write", 0) or 0
        tin  += inp;  tout += out;  tcr += cr;  tcw += cw
        cost += (inp / 1_000_000) * p["in"]
        cost += (out / 1_000_000) * p["out"]
        cost += (cr  / 1_000_000) * p["cache_read"]
        cost += (cw  / 1_000_000) * p["cache_write"]
    return tin, tout, tcr, tcw, round(cost, 6)


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


def _build_performance_retrospective(recent: list, current_price: float | None) -> str:
    """Factual check: what actually happened after each past verdict. recent is newest-first."""
    if len(recent) < 2:
        return ""

    lines = ["=== PERFORMANCE RETROSPECTIVE (factual — recalibrate entry targets and direction calls) ==="]
    found = False

    for i in range(1, len(recent)):
        a = recent[i]          # older analysis
        next_a = recent[i - 1] # the analysis that came after it

        if not a.verdict or not a.current_price or not next_a.current_price:
            continue

        days = (next_a.analysis_date - a.analysis_date).days
        chg_pct = (next_a.current_price - a.current_price) / a.current_price * 100
        direction_ok = (a.verdict == "BUY" and chg_pct > 0) or (a.verdict == "SELL" and chg_pct < 0)

        line = f"  {a.analysis_date}: {a.verdict} @ ${a.current_price:.2f}"
        if a.entry_target:
            line += f" | entry target ${a.entry_target:.2f}"
        if a.exit_target:
            line += f" | exit ${a.exit_target:.2f}"
        if a.stop_loss:
            line += f" | stop ${a.stop_loss:.2f}"
        outcome = f"{'✓' if direction_ok else '✗'} {'correct' if direction_ok else 'WRONG'} direction"
        line += f"\n    → {days}d later: ${next_a.current_price:.2f} ({chg_pct:+.1f}%) — {outcome}"

        if a.stop_loss and next_a.current_price <= a.stop_loss:
            line += " ⚠ STOP LOSS TRIGGERED"
        if a.exit_target and next_a.current_price >= a.exit_target:
            line += " ✓ EXIT TARGET HIT"
        if a.verdict == "BUY" and a.entry_target and next_a.current_price < a.entry_target:
            line += f" — entry target ${a.entry_target:.2f} was never reached (set too high)"

        lines.append(line)
        found = True

    if not found:
        return ""

    if current_price and recent[0].current_price and recent[0].verdict:
        chg = (current_price - recent[0].current_price) / recent[0].current_price * 100
        lines.append(
            f"\n  Yesterday ({recent[0].analysis_date}): {recent[0].verdict} @ "
            f"${recent[0].current_price:.2f} → today ${current_price:.2f} ({chg:+.1f}%)"
        )

    lines.append(
        "\nRecalibrate based on this: were entry targets realistic? "
        "If BUY calls were followed by drops, tighten entry targets or raise conviction threshold."
    )
    return "\n".join(lines)


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
        price, (news, news_usage), events, analyst = await asyncio.gather(
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
        ripple, ripple_usage = await analyze_ripple(ticker, news, sector)
    except Exception as e:
        logger.error(f"[{ticker}] Ripple agent failed: {e}")
        ripple = "Ripple analysis unavailable."
        ripple_usage = {"input_tokens": 0, "output_tokens": 0, "cache_read": 0, "cache_write": 0, "model": "claude-sonnet-4-6"}

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

        # Factual performance retrospective — what actually happened after past verdicts
        perf_retro = _build_performance_retrospective(recent, price.current_price)

        verdict, verdict_usage = await generate_verdict(
            ticker, price, news, events, analyst, ripple, stock_mem, is_leveraged,
            recent_analyses=recent_analyses,
            last_buy_price=last_buy_price,
            signal_convergence_score=conv_score,
            convergence_details=conv_details,
            performance_retrospective=perf_retro,
        )
    except Exception as e:
        logger.error(f"[{ticker}] Verdict agent failed: {e}")
        return

    tokens_in, tokens_out, tokens_cr, tokens_cw, cost_usd = _sum_usages([
        news_usage, ripple_usage, verdict_usage,
    ])

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
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        tokens_cache_read=tokens_cr,
        tokens_cache_write=tokens_cw,
        cost_usd=cost_usd,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    logger.info(f"[{ticker}] Analysis saved. Verdict: {verdict.verdict} | tokens in={tokens_in} out={tokens_out} | cost=${cost_usd:.4f}")

    await maybe_update_stock_memory(ticker, verdict.verdict, verdict.reasoning, news, json.dumps(events), db)
    await generate_simple_fields(analysis, db)


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
