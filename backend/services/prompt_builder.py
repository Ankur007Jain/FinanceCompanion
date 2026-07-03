"""
Prompt Builder — builds the chatbot system prompt with full stock context injected.
Static base is cached. Dynamic context (today's analyses, portfolios) is per-turn.
"""
import json
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from models import StockAnalysis, StockMemory, SimulationPortfolio, WatchlistItem

_STATIC_SYSTEM = """You are FinanceCompanion — a confident, data-driven financial advisor for busy working professionals.
Behind the scenes you think like an institutional investment committee; out loud you talk like a brilliant friend.

How you think (internally, never narrated):
- Separate FACTS (the data you were given) from ASSUMPTIONS (your inference). Never present an assumption as a fact.
- Before committing, weigh the strongest BULL case against the strongest BEAR case, then take a side.
- State a confidence level when it matters (high / medium / low) and what would change your mind.
- Hunt for asymmetric setups — where the upside clearly outweighs the downside — and say so plainly.
- Never invent a number. If you don't have the data, say so and offer to search the web.

How you speak:
- Like texting a smart friend — direct, specific, no jargon, no research-report tone.
- Lead with the verdict or the direct answer, then the why.
- Always back a claim with the actual number (price, %, date) from the analysis.
- Give both sides when it's a real call: "The bull case is X; the bear case is Y; I lean ___ because ___."
- Never hedge with "it depends" without immediately committing.
- Leveraged ETFs get stricter rules — short hold, never through earnings.

Your data:
- You have tonight's full analysis for the user's tracked stocks, plus historical stock memory.
- When a ticker is in focus, you also have its deep analysis and recent day-by-day history — use it; don't re-derive.
- You can search the web (web_search tool) for anything newer than the analysis. Synthesize results with what you already have — don't just repeat them.
- Keep it concise. The user is busy.
"""


def _pct(v):
    return f"{v*100:.1f}%" if v is not None else "N/A"


def _fmt(v, decimals=2):
    """Formats a possibly-missing numeric field — nightly data collection can leave
    fields like ma_50/ma_200 null (e.g. a rate-limited fetch), and this data flows
    into an f-string on every chat turn, so a raw `:.2f` there takes down the whole
    conversation for the user, not just the one incomplete ticker."""
    return f"{v:.{decimals}f}" if v is not None else "N/A"


def _format_analysis(a: StockAnalysis, position_line: str) -> str:
    direction = "▲" if (a.day_change_pct or 0) >= 0 else "▼"
    conv = f"  Conviction:   {a.conviction_score}/100  ({a.risk_level or 'N/A'} risk, {a.confidence or 'N/A'} confidence)\n" if a.conviction_score is not None else ""
    return (
        f"  Verdict:      {a.verdict}  (entry ${a.entry_target or 'N/A'}, exit ${a.exit_target or 'N/A'})\n"
        f"  {position_line.rstrip(chr(10))}\n"
        f"{conv}"
        f"  Price:        ${_fmt(a.current_price)}  {direction}{abs(a.day_change_pct or 0):.1f}%\n"
        f"  52-Wk Range:  ${_fmt(a.week_52_low)} – ${_fmt(a.week_52_high)}  ({_fmt(a.range_position_pct, 0)}% position)\n"
        f"  MA50/MA200:   ${_fmt(a.ma_50)} / ${_fmt(a.ma_200)}\n"
        f"  RSI:          {a.rsi or 'N/A'}\n"
        f"  Analysts:     {a.analyst_consensus} ({a.analyst_count})  target ${a.target_price_mean or 'N/A'}\n"
        f"  Reasoning:    {a.reasoning or ''}\n"
    )


def _format_position(w: WatchlistItem, current_price: Optional[float]) -> str:
    """User's actual holding in this ticker — shares, cost basis, live P&L."""
    if not w.shares:
        return "Position:       Watchlist only — user does not own this stock.\n"
    cost_basis = w.shares * w.avg_cost if w.avg_cost else None
    market_value = w.shares * current_price if current_price else None
    pnl = market_value - cost_basis if (market_value is not None and cost_basis is not None) else None
    pnl_pct = (pnl / cost_basis) if (pnl is not None and cost_basis) else None
    parts = [f"Position:       {w.shares:g} shares"]
    if w.avg_cost:
        parts.append(f"@ avg cost ${w.avg_cost:.2f} (cost basis ${cost_basis:,.2f})")
    if pnl is not None:
        sign = "+" if pnl >= 0 else ""
        parts.append(f"→ market value ${market_value:,.2f}  |  P&L {sign}${pnl:,.2f} ({sign}{pnl_pct*100:.1f}%)")
    return "  ".join(parts) + "\n"


def _format_analysis_deep(a: StockAnalysis, memory: str, history: list[StockAnalysis], position_line: str) -> str:
    """Full institutional dossier for the ticker currently in focus."""
    direction = "▲" if (a.day_change_pct or 0) >= 0 else "▼"
    lines = [
        f"=== {a.ticker} — FULL ANALYSIS (as of {a.analysis_date.isoformat()}) ===",
        f"Verdict:        {a.verdict}",
        position_line.rstrip("\n"),
    ]
    if a.conviction_score is not None:
        lines.append(f"Conviction:     {a.conviction_score}/100  |  Risk: {a.risk_level or 'N/A'}  |  Confidence: {a.confidence or 'N/A'}")
    lines += [
        f"Targets:        entry ${a.entry_target or 'N/A'}  exit ${a.exit_target or 'N/A'}  stop ${a.stop_loss or 'N/A'}  hold {a.hold_period or 'N/A'}",
        f"Price:          ${_fmt(a.current_price)}  {direction}{abs(a.day_change_pct or 0):.1f}%   52wk ${_fmt(a.week_52_low)}–${_fmt(a.week_52_high)} ({_fmt(a.range_position_pct, 0)}% of range)",
        f"Technicals:     MA50 ${_fmt(a.ma_50)}  MA200 ${_fmt(a.ma_200)}  RSI {a.rsi or 'N/A'}",
        f"Valuation:      P/E {a.pe_trailing or 'N/A'} (fwd {a.pe_forward or 'N/A'})  |  analyst {a.analyst_consensus} target ${a.target_price_mean or 'N/A'}",
        f"Fundamentals:   rev growth {_pct(a.revenue_growth)}  net margin {_pct(a.profit_margin)}  ROE {_pct(a.return_on_equity)}  D/E {a.debt_to_equity or 'N/A'}",
    ]
    if a.bull_case:
        lines.append(f"Bull case:      {a.bull_case}")
    if a.bear_case:
        lines.append(f"Bear case:      {a.bear_case}")
    if a.thesis_invalidation:
        lines.append(f"Flips if:       {a.thesis_invalidation}")
    if a.reasoning:
        lines.append(f"Reasoning:      {a.reasoning}")
    if a.news_summary:
        lines.append(f"News:           {a.news_summary}")
    if a.ripple_analysis:
        lines.append(f"Ripple effects: {a.ripple_analysis}")
    if a.events_json:
        try:
            events = json.loads(a.events_json)
            upcoming = [f"{e['date']} {e['description']}" for e in events[:3]]
            if upcoming:
                lines.append(f"Events ahead:   {' | '.join(upcoming)}")
        except Exception:
            pass
    if memory:
        lines.append(f"Memory:         {memory[:500]}")
    if history:
        lines.append("Recent history (newest first):")
        for h in history:
            flag = " ⭐" if h.is_important_day else ""
            lines.append(f"  {h.analysis_date.isoformat()}:{flag} {h.verdict} ${_fmt(h.current_price)}" + (f"  [{h.importance_reason}]" if h.importance_reason else ""))
    return "\n".join(lines)


def build_system_prompt(
    user_email: str,
    db: Session,
    conversation_ticker: Optional[str] = None,
) -> tuple[str, str]:
    today = date.today()

    watchlist = db.query(WatchlistItem).filter(WatchlistItem.user_email == user_email).all()
    tickers = [w.ticker for w in watchlist]
    watchlist_map = {w.ticker: w for w in watchlist}

    analyses = db.query(StockAnalysis).filter(
        StockAnalysis.ticker.in_(tickers),
        StockAnalysis.analysis_date == today,
    ).all() if tickers else []

    memories = db.query(StockMemory).filter(StockMemory.ticker.in_(tickers)).all() if tickers else []
    memory_map = {m.ticker: m.memory_narrative for m in memories}

    portfolios = db.query(SimulationPortfolio).filter(
        SimulationPortfolio.user_email == user_email,
        SimulationPortfolio.status == "open",
    ).all()

    lines = [f"Today: {today.isoformat()}\n"]

    # Deep dossier for the ticker in focus (most prominent context)
    if conversation_ticker:
        focus = conversation_ticker.upper()
        # With a large watchlist, the focus ticker's dossier can get buried among dozens of
        # others below — spell out unambiguously which one "this stock" refers to, since
        # nothing else in the prompt marks it as the active topic vs. just more data.
        lines.append(
            f"📌 ACTIVE CONVERSATION TOPIC: {focus}. The user is chatting specifically about "
            f"{focus} right now. When they say \"this stock\", \"this share\", \"it\", or similar, "
            f"they mean {focus} — not any other ticker listed below. Lead your answer with {focus}; "
            f"only bring in other tickers if the user explicitly asks about them.\n"
        )
        focus_analysis = (
            db.query(StockAnalysis)
            .filter(StockAnalysis.ticker == focus)
            .order_by(StockAnalysis.analysis_date.desc())
            .first()
        )
        if focus_analysis:
            history = (
                db.query(StockAnalysis)
                .filter(
                    StockAnalysis.ticker == focus,
                    StockAnalysis.id != focus_analysis.id,
                )
                .order_by(StockAnalysis.analysis_date.desc())
                .limit(5)
                .all()
            )
            focus_mem = memory_map.get(focus) or ""
            if not focus_mem:
                m = db.query(StockMemory).filter(StockMemory.ticker == focus).first()
                focus_mem = m.memory_narrative if m else ""
            focus_wl = watchlist_map.get(focus)
            focus_position = (
                _format_position(focus_wl, focus_analysis.current_price)
                if focus_wl else "Position:       Not in user's watchlist.\n"
            )
            lines.append(_format_analysis_deep(focus_analysis, focus_mem, history, focus_position))
            lines.append("")

    if analyses:
        lines.append("=== TONIGHT'S ANALYSIS ===")
        for a in analyses:
            mem = memory_map.get(a.ticker, "")
            wl = watchlist_map.get(a.ticker)
            position_line = _format_position(wl, a.current_price) if wl else "Position:       Not in user's watchlist.\n"
            lines.append(f"\n{a.ticker}:")
            lines.append(_format_analysis(a, position_line))
            if mem:
                lines.append(f"  Memory:       {mem[:300]}")
            if a.events_json:
                try:
                    events = json.loads(a.events_json)
                    upcoming = [f"{e['date']} {e['description']}" for e in events[:3]]
                    if upcoming:
                        lines.append(f"  Events ahead: {' | '.join(upcoming)}")
                except Exception:
                    pass
    else:
        lines.append("No analysis available for today yet — nightly run may not have completed.")

    if portfolios:
        lines.append("\n=== OPEN SIMULATION POSITIONS ===")
        for p in portfolios:
            lines.append(f"  {p.ticker} [{p.mode}]  {p.shares} shares @ ${p.entry_price:.2f}")

    if not tickers:
        lines.append("\nUser has no stocks in their watchlist yet.")

    dynamic_context = "\n".join(lines)
    return _STATIC_SYSTEM, dynamic_context
