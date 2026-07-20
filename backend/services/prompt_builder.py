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
9. If the user asks "did you save that" / "what do you remember about me" / anything about what's been saved, check the actual "THINGS TO REMEMBER ABOUT THIS USER" list and any per-ticker notes currently in your context — that's the real, current state, not a guess. If it's genuinely there, confirm it and quote it back. If it's not there, say so plainly ("I don't see that saved — want me to save it now?") rather than assuming you saved it because you remember saying you would.
10. Tonight's official verdict for a ticker (from its dossier) is the app's one canonical, cross-checked call — never contradict it silently. If your own read of the conversation leans a different direction (e.g. tonight's verdict is HOLD but the discussion is pointing you toward SELL), say so explicitly: state the official verdict, state where you differ and why, and let the user see both rather than quietly picking one. Two systems disagreeing without saying so is worse than either one being wrong alone.
11. Notes marked "(added by user, unverified)" are the user's own claim, typed in directly — not something this app generated or cross-checked, unlike the dossier data above it. Treat it as their input, not confirmed fact: if it's decision-relevant and checkable, offer to verify it with web_search; if it conflicts with the app's own data, say so explicitly rather than silently trusting either side.
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
    ticker_learnings = _ticker_learnings_section(ticker, db, user_email)
    return dossier + correlated + ticker_learnings


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


def _ticker_learnings_section(ticker: str, db: Session, user_email: str) -> str:
    """Personal notes this user saved specifically about this ticker (save_learning
    with ticker set) — e.g. "already knows SLV/GLD overlap, don't re-explain." Only
    shown when this ticker is actually in the dossier, unlike global learnings which
    show up everywhere — keeps context lean for tickers with no personal notes."""
    rows = (
        db.query(UserLearning)
        .filter(UserLearning.user_email == user_email, UserLearning.ticker == ticker)
        .order_by(UserLearning.created_at.desc())
        .limit(10)
        .all()
    )
    if not rows:
        return ""
    lines = ["\n\nThings you've told me about this ticker specifically:"]
    for r in reversed(rows):
        tag = " (added by user, unverified)" if r.source == "user" else ""
        lines.append(f"  - {r.learning}{tag}")
    return "\n".join(lines)


def build_user_learnings_block(user_email: str, db: Session) -> str:
    """Durable, ticker-independent (global) facts/preferences this user has explicitly
    asked to have remembered (save_learning tool with no ticker) — surfaced in every
    conversation, not just the one where it was said. Ticker-scoped learnings
    (ticker set) are handled separately by _ticker_learnings_section, only shown when
    that specific ticker's dossier is built. Capped to the most recent 15: meant to be
    a short, high-signal list the model actually applies, not an ever-growing dump.

    Deliberately its OWN cache_control block, not folded into dynamic_context: a user
    can save a new learning mid-conversation, and dynamic_context can be tens of
    thousands of tokens (ticker dossiers, correlations, watchlist). Without this split,
    saving one learning would bust the cache for that whole block on every subsequent
    turn — this way only the small learnings block needs a fresh cache_write."""
    learnings = (
        db.query(UserLearning)
        .filter(UserLearning.user_email == user_email, UserLearning.ticker.is_(None))
        .order_by(UserLearning.created_at.desc())
        .limit(15)
        .all()
    )
    if not learnings:
        return ""
    lines = ["=== THINGS TO REMEMBER ABOUT THIS USER (told to you in a past conversation) ==="]
    for learning in reversed(learnings):
        tag = " (added by user, unverified)" if learning.source == "user" else ""
        lines.append(f"- {learning.learning}{tag}")
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

    focus = conversation_ticker.upper() if conversation_ticker else None

    # The focus ticker's full dossier is NOT embedded here anymore — it's built
    # separately (build_ticker_dossier, called directly by streaming.py) as its own
    # cache_control block. Anthropic's prompt caching matches an exact PREFIX up to
    # each cache_control marker, not each block independently — if the focus dossier
    # (which necessarily differs every time the user switches which ticker they're
    # viewing) were embedded in THIS block, it would poison the cache match for
    # everything in this block too, even the compact list below which is otherwise
    # identical across every ticker-scoped conversation this user has. Keeping this
    # block dossier-free means it can be cached ONCE and reused across all of them —
    # confirmed via real data: this block was 71% of the total dynamic_context for a
    # user with 83 tracked tickers, previously rewritten from scratch on every switch.

    if analyses:
        # Every tracked ticker gets a numeric-only line (not excluding the one in
        # focus, even though its full dossier is shown elsewhere) — cheap enough to
        # send for all of them (portfolio-wide screening still works: P&L, RSI,
        # targets, important-day flag), while the expensive prose (reasoning, memory,
        # news) is a get_stock_analysis tool call away. Deliberately NOT skipping the
        # focus ticker here (a small, ~150-char redundancy) so this block's content is
        # byte-identical regardless of which ticker is in focus — that's what makes it
        # cacheable across different ticker-scoped conversations for the same user.
        # A general (non-ticker) conversation is the one place full per-ticker detail
        # is genuinely the point — that stays exactly as before.
        lines.append("=== TONIGHT'S ANALYSIS ===" if not focus else "=== ALL TRACKED TICKERS (compact — ask for detail on any of these) ===")
        for a in analyses:
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
