# Verdict Trust Strategy — Building Full Confidence for Busy Professionals

## Who We Are Serving

Doctors, nurses, engineers, teachers — people who give their days and nights to serving others. They have savings but no time to research. They don't check their finances for months. They are not day traders. They need a system they can trust completely: get introduced at a low price, get out at a higher price, and not lose sleep in between.

**The product isn't stock analysis. It's permission to stop worrying about money.**

---

## The Problem With the Current System

The current nightly analysis outputs a verdict (BUY/SELL/WATCH/HOLD) with conviction score, bull/bear cases, and price targets. That's a Bloomberg terminal output — useful for traders, overwhelming for the target user.

When a nurse opens this app on Sunday night and sees "BUY NFLX — conviction 78/100," her actual questions are:

- Did I miss the move already? Is now still a good entry?
- If I buy tomorrow and don't look for 3 months, will I be okay?
- How much of my savings should I put in?
- What's the realistic worst case — could I lose 30%?
- When do I know it's time to get out?

**None of these are answered today.**

---

## What Successful Systems Do

| System | Key Trust Mechanism |
|--------|---------------------|
| **IBD (Investor's Business Daily)** | Single composite score 1–99. Busy people act on the number, not the data behind it. |
| **Motley Fool Stock Advisor** | 3–5 year horizon picks. Monthly cadence. "Best Buys Now" tells you which picks are still at a good entry today. |
| **Goldman / Morgan Stanley** | 12-month price target with Bull / Base / Bear scenarios and probabilities. |
| **Warren Buffett** | Doesn't say BUY — says "at what price I'd buy." Margin of safety is the answer to "is now a good time?" |
| **Betterment / Wealthfront** | Whole product is "trust us, don't look, we'll handle it." High-signal, infrequent communication. |

**Common thread:** All of these systems reduce cognitive load. They answer the "so what do I actually do?" question explicitly.

---

## The Five Features That Change Everything

### 1. Entry Quality Signal
**The question it answers:** "Is now a good time to enter, or did I miss the move?"

Computed from: RSI position, distance from 200-day MA, 52-week range position, recent price momentum.

Output — one of three:
- **GREAT ENTRY** — stock is oversold or near strong support, good risk/reward
- **FAIR ENTRY** — reasonable, not ideal, proceed with smaller position
- **WAIT FOR PULLBACK** — stock is extended, better to wait for a dip

This is the single most actionable signal for someone who hasn't checked in 2 months.

---

### 2. The 90-Day Scenario
**The question it answers:** "What's realistically going to happen?"

For every BUY verdict, generate three scenarios with estimated probabilities:

- **Bull case (30%):** +22% — earnings beat + sector tailwind continuing
- **Base case (50%):** +8% — steady growth, no major catalysts
- **Bear case (20%):** -14% — macro headwind, tests support level

Probabilities derived from: analyst price target spread, historical volatility, conviction score, and macro context. Directional accuracy matters more than precision.

---

### 3. "Safe to Ignore" Rating
**The question it answers:** "Can I buy this and not look for 90 days?"

Penalizes:
- Earnings report within 30 days (high binary risk)
- Beta > 1.5 (too volatile)
- High short interest (squeeze/collapse risk)
- Leveraged ETFs (decay, not for long holds)
- Thin analyst coverage (less visibility)

Rewards:
- Low historical volatility
- Strong institutional ownership
- Wide moat sector (healthcare, consumer staples, quality tech)
- Clear technical support level below current price

Output: **HOLD-AND-FORGET / CHECK-MONTHLY / WATCH-CLOSELY**

---

### 4. Position Sizing Guidance
**The question it answers:** "How much of my portfolio should I put here?"

No current system in the app answers this. Every financial advisor considers this the most important question.

Formula basis:
- Higher conviction → larger suggested allocation
- Higher risk level → smaller suggested allocation
- Earnings proximity → smaller suggested allocation
- Already holding similar sector → suggest smaller to avoid concentration

Output: "Suggest 5–8% of your portfolio at this risk level."

---

### 5. The "Don't Panic" Protocol
**The question it answers:** "It's down 15% — do I sell or hold?"

This is the moment trust is earned or lost. When a stock in the watchlist drops 15%+ since the last BUY verdict, the nightly agent generates a specific intervention — not just a new verdict, but a direct message:

> "NFLX is down 18% since we called BUY at $680. Here's what changed: [X]. Here's what didn't change: [Y]. Your stop loss is at $580 — we haven't hit it. The thesis is intact. Recommended action: HOLD."

Or if the thesis is broken:
> "The earnings miss changes our view. We're moving to SELL. Exit plan: [details]."

Everyone can be right in a bull market. The test is what you say when it goes red. **This is where the product either keeps users forever or loses them.**

---

## Longer Term: Historical Pattern Match

Once the system has 60+ days of its own stored verdicts and outcomes:

> "Last 4 times NFLX had RSI below 42 + earnings beat in prior quarter, it returned an average of +19% over the following 90 days (3 out of 4 occurrences)."

This is backtestable on the existing `stock_analyses` table. Cannot build it until sufficient history accumulates — but the data is already being stored correctly today.

---

## Implementation Summary

All five features are additions to the **Verdict Agent** (claude-sonnet-4-6) prompt and new fields on `StockAnalysis`. No new tables, no new agents.

| Feature | New DB Fields | How Computed |
|---------|--------------|--------------|
| Entry Quality | `entry_quality` | Claude from RSI, range_position_pct, MA200 distance |
| 90-Day Scenarios | `scenario_bull/base/bear` + `_pct` + `_prob` | Claude from analyst targets, conviction, volatility |
| Hold-and-Forget | `hold_and_forget_rating` | Claude from beta, earnings proximity, leverage flag |
| Position Sizing | `position_size_pct` | Claude from conviction × inverse risk |
| Don't Panic | `dont_panic_note` | Triggered when price < last_buy_price × 0.85 |

---

## The North Star Experience

A busy professional opens the app once a month. They see:

> **NFLX — BUY**
> Entry: Great · Hold & Forget ✓ · Position: 6% of portfolio
> Bull +24% (30%) / Base +9% (50%) / Bear -11% (20%)
> "Last checked 28 days ago. Thesis intact. No action needed."

That's the experience. That's what earns trust from the people who deserve it most.
