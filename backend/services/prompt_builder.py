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

Your personality:
- You are like a brilliant friend who happens to be a finance expert
- You give direct, specific advice with exact numbers — never vague
- You never say "it depends" without immediately committing to a position
- You ground every recommendation in the analysis data you already have
- When you don't know something, you say so and offer to search for it
- You understand leveraged ETFs require different rules (short hold, no earnings overnight)

Your capabilities:
- You have access to tonight's full analysis for all tracked stocks
- You remember historical context from stock memory
- You can search the web for current information when needed (use the web_search tool)
- When you search, synthesize the result with the existing analysis — don't just repeat it

Format:
- Lead with the verdict or direct answer
- Use specific numbers (prices, percentages, dates)
- Keep responses concise — the user is busy
- Never add unnecessary caveats or disclaimers
"""


def _format_analysis(a: StockAnalysis) -> str:
    direction = "▲" if (a.day_change_pct or 0) >= 0 else "▼"
    return (
        f"  Verdict:      {a.verdict}  (entry ${a.entry_target or 'N/A'}, exit ${a.exit_target or 'N/A'})\n"
        f"  Price:        ${a.current_price:.2f}  {direction}{abs(a.day_change_pct or 0):.1f}%\n"
        f"  52-Wk Range:  ${a.week_52_low:.2f} – ${a.week_52_high:.2f}  ({a.range_position_pct:.0f}% position)\n"
        f"  MA50/MA200:   ${a.ma_50:.2f} / ${a.ma_200:.2f}\n"
        f"  RSI:          {a.rsi or 'N/A'}\n"
        f"  Analysts:     {a.analyst_consensus} ({a.analyst_count})  target ${a.target_price_mean or 'N/A'}\n"
        f"  Reasoning:    {a.reasoning or ''}\n"
    )


def build_system_prompt(
    user_email: str,
    db: Session,
    conversation_ticker: Optional[str] = None,
) -> tuple[str, str]:
    today = date.today()

    watchlist = db.query(WatchlistItem).filter(WatchlistItem.user_email == user_email).all()
    tickers = [w.ticker for w in watchlist]

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

    if analyses:
        lines.append("=== TONIGHT'S ANALYSIS ===")
        for a in analyses:
            mem = memory_map.get(a.ticker, "")
            lines.append(f"\n{a.ticker}:")
            lines.append(_format_analysis(a))
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
