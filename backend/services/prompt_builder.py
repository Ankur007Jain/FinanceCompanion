"""
Prompt Builder — builds the chatbot system prompt with full stock context injected.
Static base is cached. Dynamic context (today's analyses, portfolios) is per-turn.
"""
import json
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from models import StockAnalysis, StockMemory, SimulationPortfolio, WatchlistItem, TickerCorrelation, UserLearning

_STATIC_SYSTEM = """<role>
You are Finance Companion, a confident, data-driven AI financial advisor for busy working professionals. Internally you reason like an institutional investment committee; externally you talk like a sharp, direct friend texting a quick take.
</role>

<reasoning_rules>
Apply these before answering — never narrate them, just apply them:
1. Separate FACTS (data given to you) from ASSUMPTIONS (your inference). Never state an assumption as a fact.
2. Weigh the strongest bull case against the strongest bear case, then take a side — no fence-sitting.
3. State a confidence level (high / medium / low) tied to something concrete: signal convergence, data conflicts, or thin history — not a vibe. Default to stating it; only skip when the data is genuinely one-sided.
4. Actively look for asymmetric setups (upside clearly outweighs downside) and call them out directly.
5. Never invent a number. If data is missing, say so explicitly and offer to search the web for it.
6. Leveraged ETFs follow stricter rules: short hold periods only, never hold through earnings.
7. Don't just answer the literal question — before responding, check whether there's a risk, catalyst, or contradiction in the data the user's question doesn't mention but would change their decision if they knew it. Surface it in one sentence, even if unasked.
8. If web_search fails, returns nothing useful, or you simply don't have current information on something time-sensitive (executive changes, recent news, current prices, anything that could have changed since your training cutoff), say so explicitly — "I don't have current data on that." Never substitute your own general/training knowledge for current information and present it as if it were fresh — that's how stale facts (an executive who's since been replaced, a price that's since moved) get stated with false confidence.
</reasoning_rules>

<voice>
- Text-message tone: direct, specific, zero jargon, zero research-report phrasing.
- Lead with the verdict or direct answer first, the reasoning after.
- Every claim must cite a real number from the data (price, %, date) — no vague qualifiers.
- For genuine two-sided calls, use this shape: "Bull case is X; bear case is Y; I lean ___ because ___."
- Never hedge with "it depends" unless immediately followed by a firm lean.
- Keep it short — the user is busy. The UI renders markdown, so use it to aid scanning: bold key numbers, use a short bullet list when comparing discrete points (bull vs. bear, multiple tickers). Don't manufacture headers or sections for a quick one-line answer.
</voice>

<data_access>
- You have tonight's full analysis for the user's tracked stocks, plus historical stock memory.
- When a ticker is in focus, you also have its deep analysis and day-by-day history below — use it directly, don't re-derive conclusions from raw fields.
- Other tracked tickers are given as compact figures only (verdict, position, targets, RSI, conviction) — no reasoning or memory. If the user asks about one of them specifically, call get_stock_analysis(ticker) to get the same full depth as the focus ticker rather than guessing from the summary alone. It works for any ticker, not just ones the user tracks.
- Use web_search only for what get_stock_analysis can't answer — anything more recent than tonight's analysis, or genuinely outside our own data. Don't search the web for something our own analysis already covers.
</data_access>
"""


def _pct(v):
    return f"{v*100:.1f}%" if v is not None else "N/A"


def _pctnum(v):
    """For fields already stored as a percentage (e.g. stock_52w_change=18.4 meaning 18.4%),
    unlike _pct() which expects a fraction like 0.184."""
    return f"{v:+.1f}%" if v is not None else "N/A"


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


def _format_analysis_compact(a: StockAnalysis, position_line: str) -> str:
    """Numeric-only summary for tickers other than the one in focus, in a ticker-scoped
    conversation. Keeps every field a user might screen across their whole portfolio —
    P&L, day move, conviction, targets, RSI, 52w position, MA50/200, analyst target,
    upcoming events, the ⭐ important-day flag — and drops only the prose (reasoning,
    memory, news) that's expensive and only valuable once they're actually asking about
    this specific ticker. That's a get_stock_analysis tool call away the moment they do.

    Sector/category and a short ripple snippet ride along too — cheap (a few hundred
    tokens across a whole watchlist) but enough for the model to make a cross-ticker
    connection unprompted (e.g. MU's ripple text naming NVIDIA, with NVDA sitting right
    there in the same list) instead of needing a separate classifier to find it."""
    direction = "▲" if (a.day_change_pct or 0) >= 0 else "▼"
    flag = " ⭐" if a.is_important_day else ""
    conv = f"{a.conviction_score}/100" if a.conviction_score is not None else "N/A"
    position = position_line.strip().removeprefix("Position:").strip()
    sector = f"  [{a.sector}]" if a.sector else ""
    events = ""
    if a.events_json:
        try:
            evs = json.loads(a.events_json)
            upcoming = [f"{e['date']} {e['description']}" for e in evs[:2]]
            if upcoming:
                events = "  Events: " + " | ".join(upcoming)
        except Exception:
            pass
    ripple = ""
    if a.ripple_analysis:
        snippet = a.ripple_analysis.strip()[:120]
        ripple = f"  Ripple: {snippet}{'…' if len(a.ripple_analysis.strip()) > 120 else ''}"
    return (
        f"{a.verdict}{flag}{sector}  {position}  "
        f"${_fmt(a.current_price)} {direction}{abs(a.day_change_pct or 0):.1f}%  "
        f"Conv {conv}  RSI {a.rsi or 'N/A'}  52wk-pos {_fmt(a.range_position_pct, 0)}%  "
        f"MA50/200 ${_fmt(a.ma_50)}/${_fmt(a.ma_200)}  "
        f"targets: entry ${a.entry_target or 'N/A'} exit ${a.exit_target or 'N/A'} stop ${a.stop_loss or 'N/A'}  "
        f"Analyst {a.analyst_consensus or 'N/A'} tgt ${a.target_price_mean or 'N/A'}{events}{ripple}"
    )


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
        f"Long-term:      1yr {_pctnum(a.stock_52w_change)} (S&P {_pctnum(a.sp500_52w_change)})   5yr {_pctnum(a.stock_5y_change)} (S&P {_pctnum(a.sp500_5y_change)})",
        f"Valuation:      P/E {a.pe_trailing or 'N/A'} (fwd {a.pe_forward or 'N/A'})  |  analyst {a.analyst_consensus} ({a.analyst_count or 'N/A'}) target ${a.target_price_mean or 'N/A'} (${a.target_price_low or 'N/A'}–${a.target_price_high or 'N/A'})",
        f"Fundamentals:   rev growth {_pct(a.revenue_growth)}  net margin {_pct(a.profit_margin)}  ROE {_pct(a.return_on_equity)}  D/E {a.debt_to_equity or 'N/A'}  FCF {a.free_cashflow or 'N/A'}  beta {a.beta or 'N/A'}",
        f"Ownership:      Inst {_pct(a.inst_ownership_pct)}  Insider {_pct(a.insider_ownership_pct)}  Short float {_pct(a.short_float_pct)} ({a.short_ratio or 'N/A'} days to cover)",
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
    if a.data_conflicts:
        lines.append(f"Data caution:   {a.data_conflicts}")
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


def build_ticker_dossier(ticker: str, db: Session, user_email: str) -> str:
    """Full institutional dossier for any ticker — same content whether it's the
    conversation's initial focus or one the user pivots to mid-chat via the
    get_stock_analysis tool, so quality never depends on which path got you here."""
    ticker = ticker.upper()
    analysis = (
        db.query(StockAnalysis)
        .filter(StockAnalysis.ticker == ticker)
        .order_by(StockAnalysis.analysis_date.desc())
        .first()
    )
    if not analysis:
        return f"No analysis available yet for {ticker}."

    history = (
        db.query(StockAnalysis)
        .filter(StockAnalysis.ticker == ticker, StockAnalysis.id != analysis.id)
        .order_by(StockAnalysis.analysis_date.desc())
        .limit(5)
        .all()
    )
    mem_row = db.query(StockMemory).filter(StockMemory.ticker == ticker).first()
    memory = mem_row.memory_narrative if mem_row else ""

    wl = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_email == user_email, WatchlistItem.ticker == ticker)
        .first()
    )
    position_line = (
        _format_position(wl, analysis.current_price)
        if wl else "Position:       Not in user's watchlist.\n"
    )
    dossier = _format_analysis_deep(analysis, memory, history, position_line)
    correlated = _correlated_tickers_section(ticker, db, user_email)
    return dossier + correlated if correlated else dossier


def _correlated_tickers_section(ticker: str, db: Session, user_email: str) -> str:
    """Which OTHER tickers this user tracks move with (or against) this one, beyond
    what's explained by general market direction. Only pairs that survived
    Benjamini-Hochberg FDR correction (see scripts/compute_correlations.py) are
    stored as significant=True — everything else is deliberately withheld here so
    chat never presents a correlation that might just be noise as if it were real."""
    watchlist = {w.ticker for w in db.query(WatchlistItem).filter(WatchlistItem.user_email == user_email).all()}
    if not watchlist:
        return ""

    rows = (
        db.query(TickerCorrelation)
        .filter(
            TickerCorrelation.significant.is_(True),
            (TickerCorrelation.ticker_a == ticker) | (TickerCorrelation.ticker_b == ticker),
        )
        .order_by(TickerCorrelation.computed_date.desc())
        .all()
    )
    if not rows:
        return ""

    latest_date = rows[0].computed_date
    seen = set()
    matches = []
    for r in rows:
        if r.computed_date != latest_date:
            continue
        other = r.ticker_b if r.ticker_a == ticker else r.ticker_a
        if other == ticker or other in seen or other not in watchlist:
            continue
        seen.add(other)
        matches.append((other, r.corr_90d))

    if not matches:
        return ""
    matches.sort(key=lambda m: abs(m[1] or 0), reverse=True)
    lines = [f"\n\nCorrelated in your portfolio (market-beta-adjusted, 90d, as of {latest_date}):"]
    for other, corr in matches[:5]:
        direction = "moves with" if (corr or 0) >= 0 else "moves against (potential hedge)"
        lines.append(f"  {other}: {corr:+.2f} — {direction} {ticker}")
    return "\n".join(lines)


def build_system_prompt(
    user_email: str,
    db: Session,
    conversation_ticker: Optional[str] = None,
) -> tuple[str, str]:
    today = date.today()

    # Ordered explicitly (not just for display) — this text becomes part of the cached
    # system prompt, and an unordered .in_() query has no guaranteed row order between
    # calls, which silently breaks Anthropic's exact-prefix cache match on every turn.
    watchlist = db.query(WatchlistItem).filter(
        WatchlistItem.user_email == user_email
    ).order_by(WatchlistItem.ticker).all()
    tickers = [w.ticker for w in watchlist]
    watchlist_map = {w.ticker: w for w in watchlist}

    analyses = db.query(StockAnalysis).filter(
        StockAnalysis.ticker.in_(tickers),
        StockAnalysis.analysis_date == today,
    ).order_by(StockAnalysis.ticker).all() if tickers else []

    memories = db.query(StockMemory).filter(
        StockMemory.ticker.in_(tickers)
    ).order_by(StockMemory.ticker).all() if tickers else []
    memory_map = {m.ticker: m.memory_narrative for m in memories}

    portfolios = db.query(SimulationPortfolio).filter(
        SimulationPortfolio.user_email == user_email,
        SimulationPortfolio.status == "open",
    ).order_by(SimulationPortfolio.ticker).all()

    lines = [f"Today: {today.isoformat()}\n"]

    # Durable, ticker-independent facts/preferences this user has explicitly asked to
    # have remembered (save_learning tool) — surfaced in every conversation, not just
    # the one where it was said. Capped to the most recent 15: this is meant to be a
    # short, high-signal list the model actually applies, not an ever-growing dump.
    learnings = (
        db.query(UserLearning)
        .filter(UserLearning.user_email == user_email)
        .order_by(UserLearning.created_at.desc())
        .limit(15)
        .all()
    )
    if learnings:
        lines.append("=== THINGS TO REMEMBER ABOUT THIS USER (told to you in a past conversation) ===")
        for learning in reversed(learnings):
            lines.append(f"- {learning.learning}")
        lines.append("")

    focus = conversation_ticker.upper() if conversation_ticker else None

    # Deep dossier for the ticker in focus (most prominent context)
    if focus:
        # With a large watchlist, the focus ticker's dossier can get buried among dozens of
        # others below — spell out unambiguously which one "this stock" refers to, since
        # nothing else in the prompt marks it as the active topic vs. just more data.
        lines.append(
            f"📌 ACTIVE CONVERSATION TOPIC: {focus}. The user is chatting specifically about "
            f"{focus} right now. When they say \"this stock\", \"this share\", \"it\", or similar, "
            f"they mean {focus} — not any other ticker listed below. Lead your answer with {focus}; "
            f"only bring in other tickers if the user explicitly asks about them.\n"
        )
        lines.append(build_ticker_dossier(focus, db, user_email))
        lines.append("")

    if analyses:
        # In a ticker-scoped conversation, every OTHER ticker gets a numeric-only line —
        # cheap enough to send for all of them (portfolio-wide screening still works: P&L,
        # RSI, targets, important-day flag), while the expensive prose (reasoning, memory,
        # news) is a get_stock_analysis tool call away the moment the user actually asks
        # about one specifically. A general (non-ticker) conversation is the one place full
        # per-ticker detail is genuinely the point — that stays exactly as before.
        lines.append("=== TONIGHT'S ANALYSIS ===" if not focus else "=== OTHER TRACKED TICKERS (compact — ask for detail on any of these) ===")
        for a in analyses:
            if focus and a.ticker.upper() == focus:
                continue  # already shown in full above
            wl = watchlist_map.get(a.ticker)
            position_line = _format_position(wl, a.current_price) if wl else "Position:       Not in user's watchlist.\n"
            if focus:
                lines.append(f"{a.ticker}: {_format_analysis_compact(a, position_line)}")
                continue
            mem = memory_map.get(a.ticker, "")
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
