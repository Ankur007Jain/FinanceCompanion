"""
Verdict Agent — synthesizes all agent outputs into a final, actionable recommendation.
Uses Claude Sonnet. Actively checks for contradictions between signals before issuing verdict.
"""
import json
import os
from dataclasses import dataclass
from typing import Optional

import anthropic

from agents.price_agent import PriceData
from agents.analyst_agent import AnalystData

_SONNET = "claude-sonnet-4-6"

_SYSTEM = """You are FinanceCompanion's advisor — and behind the scenes, an institutional investment committee.

Before you write a single word, run this committee process internally (do NOT output the steps):
1. SNAPSHOT — read price, position in 52-week range, volume vs average.
2. TECHNICALS — trend from MA50/MA200 and RSI. Above both MAs = uptrend; below = downtrend. RSI>70 = run up fast; RSI<30 = beaten down.
3. FUNDAMENTALS — valuation (P/E vs growth), profitability (margins, ROE), health (debt, free cash flow).
4. SENTIMENT & CATALYSTS — the news summary, ripple effects, and upcoming events.
5. VALUATION — analyst mean target vs current price (the upside %).
6. MOAT & RISK — competitive durability and the single biggest thing that could go wrong.
7. SELF-CHALLENGE — argue the strongest BULL case, then the strongest BEAR case, then decide which wins.
8. CONVICTION — score 0-100 on how strong the setup is; assign risk LOW/MED/HIGH; state your confidence.
9. BUSY PROFESSIONAL SIGNALS — answer four questions a non-expert would actually ask:
   - entry_quality: Is now a good time to enter? GREAT = oversold/near support, excellent risk-reward. FAIR = reasonable but not ideal. WAIT = extended/overbought, better to wait for a pullback.
   - hold_and_forget_rating: Can they buy and ignore for 90 days? HOLD_AND_FORGET = low volatility, no near-term binary events, strong fundamentals. CHECK_MONTHLY = moderate risk, worth a monthly glance. WATCH_CLOSELY = earnings within 30 days, high beta, leveraged, or thesis at risk.
   - position_size_pct: What fraction of their portfolio? Scale with conviction and inverse of risk. E.g. HIGH conviction + LOW risk = "7-10%". LOW conviction + HIGH risk = "2-3%".
   - scenarios: Give three honest probability-weighted outcomes over 90 days. Bull + Base + Bear probabilities must sum to 100. Be realistic — base case is the most likely, not the best case.

Discipline rules:
- Weigh bull vs bear honestly before committing. If signals are weak or contradictory, issue WATCH — no advice beats wrong advice.
- Never invent a number. Use only the data given. If something is missing, reason without it; don't fabricate.
- Leveraged ETFs: stricter rules — max hold 1-3 days, never hold through earnings.

Then SPEAK to the user — a busy working professional, not a finance expert:
- Write like you're texting a smart friend, not writing a research report.
- No jargon. Replace finance terms with plain words:
    "RSI overbought" → "the stock has run up fast and may be due for a pullback"
    "trading below 200-day MA" → "below where it averaged over the past year — a weak sign"
    "headwinds" → "challenges" or just name the specific problem
    "catalyst" → "reason to move" or "trigger"
    "bullish/bearish" → "likely to go up / likely to go down"
- When citing a news event, name the source and include the URL if one was provided.
- When citing a price level or ratio, include the actual number.
- bull_case / bear_case / thesis_invalidation must each be ONE plain-English sentence.
- Never hedge with "it depends" — commit.
- Output must be valid JSON matching the schema exactly. No prose outside the JSON.
"""

_SCHEMA = """{
  "verdict": "BUY|HOLD|SELL|WATCH",
  "entry_target": <float or null>,
  "exit_target": <float or null>,
  "stop_loss": <float or null>,
  "hold_period": "<e.g. '3-5 days', '2-4 weeks', '1-3 months', or null if WATCH/SELL>",
  "reasoning": "<2-3 sentences, specific and confident, plain English>",
  "conviction_score": <integer 0-100, how strong the overall setup is>,
  "risk_level": "LOW|MED|HIGH",
  "confidence": "High|Medium|Low",
  "bull_case": "<one plain-English sentence — the strongest reason this works>",
  "bear_case": "<one plain-English sentence — the strongest reason this fails>",
  "thesis_invalidation": "<one sentence — the single event that would flip this verdict>",
  "conflict_flags": "<any contradictions between signals, or empty string>",
  "is_important_day": <true|false>,
  "importance_reason": "<why this day is significant, or empty string>",

  "entry_quality": "GREAT|FAIR|WAIT",
  "hold_and_forget_rating": "HOLD_AND_FORGET|CHECK_MONTHLY|WATCH_CLOSELY",
  "position_size_pct": "<e.g. '5-8%' — suggested portfolio allocation at this risk level>",

  "scenario_bull": "<one sentence — what happens in the bull case>",
  "scenario_bull_pct": <float — expected % return in bull case, e.g. 22.5>,
  "scenario_bull_prob": <integer 0-100 — probability of bull case>,

  "scenario_base": "<one sentence — what happens in the base case>",
  "scenario_base_pct": <float — expected % return in base case>,
  "scenario_base_prob": <integer 0-100 — probability of base case>,

  "scenario_bear": "<one sentence — what happens in the bear case>",
  "scenario_bear_pct": <float — expected % return in bear case, negative number>,
  "scenario_bear_prob": <integer 0-100 — probability of bear case>,

  "dont_panic_note": "<if price dropped >15% since last BUY, address it directly and plainly: what changed, what didn't, whether to hold or exit. Otherwise empty string.>"
}"""


@dataclass
class VerdictResult:
    verdict: str
    entry_target: Optional[float]
    exit_target: Optional[float]
    stop_loss: Optional[float]
    hold_period: Optional[str]
    reasoning: str
    conflict_flags: str
    is_important_day: bool = False
    importance_reason: str = ""
    conviction_score: Optional[int] = None
    risk_level: str = ""
    confidence: str = ""
    bull_case: str = ""
    bear_case: str = ""
    thesis_invalidation: str = ""
    # Trust layer
    entry_quality: str = ""
    hold_and_forget_rating: str = ""
    position_size_pct: str = ""
    scenario_bull: str = ""
    scenario_base: str = ""
    scenario_bear: str = ""
    scenario_bull_pct: Optional[float] = None
    scenario_base_pct: Optional[float] = None
    scenario_bear_pct: Optional[float] = None
    scenario_bull_prob: Optional[int] = None
    scenario_base_prob: Optional[int] = None
    scenario_bear_prob: Optional[int] = None
    dont_panic_note: str = ""


async def generate_verdict(
    ticker: str,
    price: PriceData,
    news: str,
    events: list[dict],
    analyst: AnalystData,
    ripple: str,
    stock_memory: str,
    is_leveraged: bool = False,
    recent_analyses: list[dict] | None = None,
    last_buy_price: Optional[float] = None,
    signal_convergence_score: int = 0,
    convergence_details: dict | None = None,
) -> VerdictResult:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return VerdictResult(
            verdict="WATCH", entry_target=None, exit_target=None,
            stop_loss=None, hold_period=None,
            reasoning="ANTHROPIC_API_KEY not set — cannot generate verdict.",
            conflict_flags="",
        )

    history_block = ""
    if recent_analyses:
        lines = ["=== RECENT HISTORY (last 5 trading days) ==="]
        for a in recent_analyses:
            flag = " ⭐ IMPORTANT" if a.get("is_important_day") else ""
            lines.append(
                f"  {a['date']}:{flag} {a['verdict']}  ${a.get('current_price', 'N/A')}"
                + (f"  [{a.get('importance_reason', '')}]" if a.get("importance_reason") else "")
            )
        history_block = "\n".join(lines)

    direction = "▲" if price.day_change_pct >= 0 else "▼"
    events_text = "\n".join(
        f"  • {e['date']} — {e['description']}" for e in events
    ) or "  • None upcoming"

    def _pct(v):
        return f"{v*100:.1f}%" if v is not None else "N/A"

    def _fmt(v, prefix="", suffix="", decimals=2):
        return f"{prefix}{v:.{decimals}f}{suffix}" if v is not None else "N/A"

    fundamentals_block = f"""
=== FUNDAMENTALS ===
Valuation:       P/E trailing={_fmt(analyst.pe_trailing, decimals=1)}x  |  P/E forward={_fmt(analyst.pe_forward, decimals=1)}x
Growth:          Revenue={_pct(analyst.revenue_growth)} YoY  |  Earnings={_pct(analyst.earnings_growth)} YoY
Profitability:   Net margin={_pct(analyst.profit_margin)}  |  ROE={_pct(analyst.return_on_equity)}
Health:          Debt/Equity={_fmt(analyst.debt_to_equity, decimals=1)}  |  Free cashflow=${analyst.free_cashflow/1e9:.2f}B" if analyst.free_cashflow else "  Free cashflow=N/A"
Market:          Beta={_fmt(analyst.beta, decimals=2)}  |  Market cap={f"${analyst.market_cap/1e9:.1f}B" if analyst.market_cap else "N/A"}
Relative Perf:   Stock 52w={_pct(analyst.stock_52w_change)}  |  S&P 500 52w={_pct(analyst.sp500_52w_change)}
Short Interest:  {_pct(analyst.short_float_pct)} of float  |  Days to cover={_fmt(analyst.short_ratio, decimals=1)}
Ownership:       Institutions={_pct(analyst.inst_ownership_pct)}  |  Insiders={_pct(analyst.insider_ownership_pct)}
Dividend:        Yield={_pct(analyst.dividend_yield)}
Sector:          {analyst.sector or "N/A"} / {analyst.industry or "N/A"}"""

    prompt = f"""
Ticker: {ticker} {"[LEVERAGED ETF — apply strict hold rules]" if is_leveraged else ""}

=== PRICE DATA ===
Current:         ${price.current_price:.2f}  ({direction}{abs(price.day_change_pct):.1f}% today)
52-Week Range:   ${price.week_52_low:.2f} – ${price.week_52_high:.2f}
Position:        {price.range_position_pct:.0f}% of 52-week range (0=at low, 100=at high)
Volume:          {price.volume:,} vs {price.avg_volume:,} avg
50-Day MA:       ${price.ma_50:.2f}
200-Day MA:      ${price.ma_200:.2f}
RSI:             {price.rsi if price.rsi else 'N/A'}
{fundamentals_block}

=== ANALYST CONSENSUS ===
Consensus:       {analyst.consensus} ({analyst.analyst_count} analysts)
Price Target:    ${analyst.target_mean:.2f} mean  |  low ${analyst.target_low or 0:.2f}  |  high ${analyst.target_high or 0:.2f}
Upside to Mean:  {analyst.upside_pct:.1f}% vs current
{f"⚠ {analyst.conflict_notes}" if analyst.conflict_notes else ""}

=== NEWS SUMMARY ===
{news}

=== UPCOMING EVENTS ===
{events_text}

=== RIPPLE ANALYSIS ===
{ripple}

=== STOCK MEMORY (historical context) ===
{stock_memory or "No prior memory — first analysis."}

{history_block}

{f"=== DATA CONFLICTS ===" + chr(10) + price.conflict_notes if price.conflict_notes else ""}

=== SIGNAL CONVERGENCE (pre-computed, deterministic) ===
Score: {signal_convergence_score}/7 independent signals confirmed
{chr(10).join(f"  {'✓' if v else '✗'} {k.replace('_', ' ').title()}" for k, v in (convergence_details or {}).items())}

CONVICTION FLOOR RULE: If score < 5, verdict MUST be WATCH. Do not issue BUY on weak setups.
{"⚠ Score is " + str(signal_convergence_score) + "/7 — you MUST issue WATCH, not BUY." if signal_convergence_score < 5 else "✓ Score clears the threshold — BUY is eligible if analysis supports it."}

{f"""=== DON'T PANIC CHECK ===
Last BUY was issued at ${last_buy_price:.2f}. Current price is ${price.current_price:.2f} — a drop of {abs((price.current_price - last_buy_price) / last_buy_price * 100):.1f}%. Address this directly in dont_panic_note: what changed, what didn't, and whether the user should hold, add, or exit.""" if last_buy_price and price.current_price < last_buy_price * 0.85 else ""}

Based on all the above, issue a verdict. Flag is_important_day=true if today involves a verdict
reversal from prior history, major catalyst, earnings within 5 days, or index event.
If signals are weak or contradictory and you are not confident, issue WATCH — it is better
to give no advice than wrong advice. Output JSON only, matching this schema:
{_SCHEMA}
"""

    client = anthropic.AsyncAnthropic(api_key=api_key)
    resp = await client.messages.create(
        model=_SONNET, max_tokens=8192,
        system=_SYSTEM,
        messages=[
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "{"},   # prefill forces JSON output
        ],
    )
    raw = ("{" + resp.content[0].text).strip()

    # Strip markdown code fences if present (shouldn't happen with prefill but be safe)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
        conviction = data.get("conviction_score")
        def _f(k): return float(data[k]) if data.get(k) is not None else None
        def _i(k): return int(data[k]) if data.get(k) is not None else None
        return VerdictResult(
            verdict=data.get("verdict", "WATCH"),
            entry_target=data.get("entry_target"),
            exit_target=data.get("exit_target"),
            stop_loss=data.get("stop_loss"),
            hold_period=data.get("hold_period"),
            reasoning=data.get("reasoning", ""),
            conflict_flags=data.get("conflict_flags", ""),
            is_important_day=bool(data.get("is_important_day", False)),
            importance_reason=data.get("importance_reason", ""),
            conviction_score=int(conviction) if conviction is not None else None,
            risk_level=data.get("risk_level", ""),
            confidence=data.get("confidence", ""),
            bull_case=data.get("bull_case", ""),
            bear_case=data.get("bear_case", ""),
            thesis_invalidation=data.get("thesis_invalidation", ""),
            entry_quality=data.get("entry_quality", ""),
            hold_and_forget_rating=data.get("hold_and_forget_rating", ""),
            position_size_pct=data.get("position_size_pct", ""),
            scenario_bull=data.get("scenario_bull", ""),
            scenario_base=data.get("scenario_base", ""),
            scenario_bear=data.get("scenario_bear", ""),
            scenario_bull_pct=_f("scenario_bull_pct"),
            scenario_base_pct=_f("scenario_base_pct"),
            scenario_bear_pct=_f("scenario_bear_pct"),
            scenario_bull_prob=_i("scenario_bull_prob"),
            scenario_base_prob=_i("scenario_base_prob"),
            scenario_bear_prob=_i("scenario_bear_prob"),
            dont_panic_note=data.get("dont_panic_note", ""),
        )
    except Exception:
        return VerdictResult(
            verdict="WATCH",
            entry_target=None,
            exit_target=None,
            stop_loss=None,
            hold_period=None,
            reasoning=raw[:500],
            conflict_flags="JSON parse error — raw reasoning stored.",
        )
