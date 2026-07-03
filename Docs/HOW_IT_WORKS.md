# How FinanceCompanion Works — Plain English Guide

> No finance degree required. This explains what the app actually does, how it thinks, and why it works the way it does.

---

## The Big Idea

Every evening after the stock market closes, FinanceCompanion runs a full AI analysis on every stock in your watchlist. By the time you open the app in the morning, it has already done the homework — read the news, checked the numbers, looked at what analysts think, and come back with a clear verdict: **BUY, HOLD, SELL, or WATCH.**

It's like having a friend who's brilliant at finance and stays up every night studying your stocks so you don't have to.

---

## What Happens Every Night

At 11 PM Eastern, six AI agents wake up and get to work on each of your stocks — all running at the same time, in parallel:

### 1. Price Agent
Checks today's price from two independent sources (Yahoo Finance and Finnhub) and compares them. If they disagree by more than a normal rounding difference, it flags it rather than guessing. It also computes:
- Where the stock sits in its 52-week range (near the top? near the bottom?)
- How it moved today vs its average daily volume
- Moving averages (50-day and 200-day) — whether the stock is above or below its own recent average
- RSI (Relative Strength Index) — a number from 0–100 that tells whether a stock has run up too fast (above 70) or been beaten down (below 30)

### 2. News Agent
Reads today's news headlines from both sources and writes a 3–4 sentence plain-English summary of what actually matters — ignoring noise and focusing on things that could move the stock.

### 3. Event Agent
Checks what's coming up on the calendar:
- Earnings announcements (when the company reports profits/losses)
- Federal Reserve decisions (interest rate changes that move the whole market)
- Analyst upgrades or downgrades
- Index additions or removals (getting added to the S&P 500 is a big deal)

### 4. Analyst Agent
Reads what professional Wall Street analysts currently think — how many rate it Buy vs Hold vs Sell, what their average price target is, and what the upside is from today's price. Cross-validated between two sources; if they disagree, the disagreement is surfaced.

### 5. Ripple Agent
This is the most interesting one. It reads today's big news — macro events, geopolitical moves, sector announcements — and traces the chain of second and third-order effects. 

Example: A major semiconductor export restriction is announced → chips get scarce → NVIDIA's customers accelerate orders → NVIDIA revenue goes up → suppliers of chip-making equipment also benefit → but companies building data centers may face delays.

The ripple agent maps these chains across your watchlist so you understand *why* things are moving, not just *that* they're moving.

### 6. Verdict Agent
After all five agents finish, the Verdict Agent receives everything they found and runs an internal process before issuing its recommendation:

1. Looks at the price position, technicals, and volume
2. Reviews fundamentals (P/E ratio, revenue growth, profit margins, debt)
3. Reads the news summary and upcoming events
4. Considers the ripple analysis
5. Reads the stock's memory (see below) to understand its history
6. Reviews the last 5 days of verdicts and what actually happened after each one
7. Argues the strongest case FOR buying, then the strongest case AGAINST
8. Decides which side wins
9. Issues the final verdict with specific numbers

---

## What the Verdict Includes

Every analysis gives you much more than just BUY or SELL:

### The Verdict
One of four options:
- **BUY** — the AI thinks now is a good time to enter
- **HOLD** — if you own it, keep it; if not, don't rush in
- **SELL** — the AI thinks it's time to exit
- **WATCH** — signals are mixed; monitor but don't act yet

> **WATCH is a valid and useful answer.** Wrong advice is worse than no advice. If the evidence isn't clear, the AI says so instead of guessing.

### Entry Target, Exit Target, Stop Loss
Specific price levels:
- **Entry** — the price at which the setup looks favorable to buy
- **Exit** — where to take profits if it goes up
- **Stop Loss** — where to exit to protect yourself if it goes wrong

### Conviction Score (0–100)
How confident is the AI in this verdict? A score of 80+ means multiple independent signals are all pointing the same direction. A score of 45 means the analysis is more uncertain — signals are mixed.

### Bull Case / Bear Case / Thesis Invalidation
Three one-sentence answers:
- **Bull Case**: the strongest reason this works out well
- **Bear Case**: the strongest reason it doesn't
- **Thesis Invalidation**: the single event that would make the AI flip its verdict

### Entry Quality
A plain-English answer to "is right now a good moment to buy?"
- **GREAT** — stock is near support, price looks favorable, risk/reward is strong
- **FAIR** — reasonable entry but not ideal conditions
- **WAIT** — stock has run up too fast or is in a risky spot; better to wait for a pullback

### Strategy (Hold & Forget Rating)
How much attention does this position need?
- **HOLD AND FORGET** — fundamentally strong, low volatility, safe to buy and check in monthly
- **CHECK MONTHLY** — moderate risk, worth a monthly review
- **WATCH CLOSELY** — earnings coming up, high volatility, or the thesis is at risk — needs more attention

### Suggested Position Size
What percentage of your total portfolio should you put into this? The AI scales it based on conviction and risk. High conviction + low risk = larger position. Low conviction + high risk = smaller position. Example: "5–8% of your portfolio."

### Three Scenarios
The AI gives you three honest probability-weighted outcomes over the next 90 days:
- **Bull case**: e.g., "Stock climbs to $420 (+18%) if earnings beat and guidance is raised" — probability 30%
- **Base case**: e.g., "Stock holds around $360 (+1%) as market digests recent move" — probability 50%
- **Bear case**: e.g., "Stock drops to $310 (-13%) if sector rotation continues" — probability 20%

These must always add up to 100%.

### Don't Panic Note
If the stock has dropped more than 15% since the AI last issued a BUY, it addresses this directly. Not with vague comfort — with specifics: what changed, what didn't, whether you should hold, add more, or exit.

---

## Signal Convergence Score

Before calling Claude, the system runs a quick checklist of seven independent signals:

| Signal | What It Means |
|--------|--------------|
| Oversold RSI | RSI below 42 — stock may be beaten down more than it deserves |
| Near 52-week low | Stock is near the bottom of its annual range — potential value entry |
| Analyst upside >15% | Analysts think it has meaningful room to grow from here |
| No binary risk | Earnings are more than 21 days away — no surprise risk imminent |
| Positive free cash flow | Company is generating real cash, not burning through it |
| Institutional backing | Big money managers own >40% — strong vote of confidence |
| Price above 200-day MA | Stock is above its long-term average — trend is upward |

**All 7 signals are checked. If 5 or more confirm, BUY is eligible. If fewer than 5, the verdict must be WATCH.** This prevents the AI from issuing BUY signals on weak setups just because one or two things look good.

---

## The Two Sources Rule

Every important number is checked against two independent data sources — Yahoo Finance and Finnhub. They use different data pipelines, different APIs, and different companies providing the data.

If they agree → proceed.
If they meaningfully disagree → the discrepancy is flagged in the analysis. The AI never silently picks one and hides the conflict from you.

This matters because data errors happen. A single-source system might not notice. A two-source system always does.

---

## Stock Memory — The AI Remembers

Each stock has its own memory — a paragraph of prose that gets updated over time by the AI. This memory carries forward across nightly runs.

If MSFT had a major earnings miss two weeks ago and the AI flagged it as a turning point, that context is still in the memory tonight. The next verdict doesn't start from scratch — it starts with the full story of what's happened recently with that stock.

The memory is updated by a fast AI model (Haiku) each night, but only when something genuinely significant happened. If nothing important changed, the memory isn't updated.

---

## Performance Retrospective — The AI Learns from Its Mistakes

This is the self-correction mechanism. Every night, before the Verdict Agent issues a new recommendation, it first reviews what actually happened after its last several verdicts:

```
June 23: BUY @ $367 | entry target $370 | exit $415
  → 1 day later: $352 (-4.1%) — ✗ WRONG direction
  — entry target $370 was never reached (set too high)

June 24: BUY @ $373 | entry target $375
  → 1 day later: $365 (-2.3%) — ✗ WRONG direction
```

If two consecutive BUY calls were followed by price drops, the Verdict Agent sees that directly and recalibrates — tightening entry targets, raising the conviction threshold, or issuing WATCH instead of BUY.

This is how the AI gets better at a specific stock over time, not just in general.

---

## Learning from Reports

When you generate an AI report (see below), the app also runs a background process: it reads the "What the AI Got Wrong" section of the report and extracts the key lessons into the stock's memory.

So if a report identifies that the AI was consistently setting entry targets too high for MSFT during a volatile period, that lesson gets written into MSFT's memory. The next time the Verdict Agent analyzes MSFT, it starts with that context already loaded.

Human feedback closes the loop.

---

## Past Analyses — History at a Glance

When you expand a stock on the dashboard, you'll see a **PAST ANALYSES** section showing the last 7–30 days of verdicts at a glance:

```
2026-06-27  BUY  $372.97  +4.94%  RSI 18  CONVICTION 78  ⭐
  "RSI at 9 marks genuine capitulation; quality stock at rare discount — buy the dip"

2026-06-26  WATCH  $352.83  -4.1%  RSI 12  CONVICTION 65  ⭐
  "Another new low but volume suggests institutional accumulation beginning"
```

Each row shows:
- **Date** and **verdict**
- **Price** that day and **day change %** (green = up, red = down)
- **RSI** that day — was it oversold? Overbought?
- **Conviction** score — how confident was the AI?
- **⭐** — important day flag (verdict reversal, earnings nearby, major catalyst)
- **One-line reasoning snippet** — the key thought behind that day's verdict

Click any row to expand the full analysis for that day.

---

## The AI Report

The Generate Report button synthesizes the last 30 days of analysis into one readable debrief. It covers:

**Verdict Trajectory** — how did the verdict change over the period and what drove each shift?

**Conviction Trend** — was the AI growing more or less confident? Which was the highest conviction day and why?

**Price Target Accuracy** — were the entry and exit targets realistic? Did the stock actually reach them?

**Recurring Themes** — what macro factors, news patterns, or risks kept showing up?

**What the AI Got Right vs Wrong** — an honest assessment. Where were the calls accurate, where did they miss, and why?

**Watch For** — one or two specific things to monitor going forward based on the pattern.

Reports are generated once per day and cached — if you generate it at 9 AM, it's still there at 9 PM without re-running. The next day, it shows the previous report with a **STALE** badge and a Regenerate button so you can get an updated version including the newest analysis.

---

## Important Days ⭐

The AI flags certain days as "Important" when something significant happened or is about to happen:

- **Verdict reversal** — the AI switched from BUY to WATCH or SELL (or vice versa)
- **Earnings within 5 days** — a binary event is imminent
- **Major catalyst** — a significant news event, analyst rating change, or index event
- **Don't panic situation** — price dropped >15% since the last BUY

These are marked with a ⭐ star and show the reason when you hover over it. Important days are the ones worth reading carefully even if you don't read every daily analysis.

---

## Leveraged ETFs — Different Rules

Leveraged ETFs (like SOXL or MVLL) behave differently from regular stocks due to **time decay**. In a flat or choppy market, a 3x ETF loses value even if the underlying index goes nowhere. These instruments are designed for short-term swings, not long-term holding.

The AI enforces strict rules automatically for any ticker flagged as leveraged:
- **Max hold period: 1–3 days** — never intended as a long-term position
- **Never hold through earnings** — volatility from earnings can wipe out a leveraged position overnight
- **Entry quality is stricter** — the AI won't issue BUY if the stock has already run up significantly
- **Position size is smaller** — higher risk = smaller suggested allocation

---

## Smart Skip — Saving Cost Without Losing Quality

On quiet days when a stock hasn't moved meaningfully, the AI skips regenerating a full analysis and reuses yesterday's. This saves significant compute cost.

A "quiet" day for a stock means all of the following are true:
- Price changed less than 2% today
- Same verdict for the last 3 consecutive days
- No earnings or major events within the next 5 days
- Yesterday was not flagged as an important day

When a stock is skipped, the date on the analysis shows as "N days ago" so you always know the freshness of what you're looking at.

---

## The Dashboard — At a Glance

The main dashboard shows all your watchlist stocks in a compact table. For each stock, you can see at a glance:

**Collapsed row:**
- Verdict badge (BUY / HOLD / SELL / WATCH) in color
- Current price and today's % change
- S&P 500 and sector ETF change — so you immediately know if the stock is moving with or against the market
- 7-day sparkline — a tiny chart showing the price trend over the past week
- RSI pill — with a tooltip explaining what overbought/oversold means in plain English

**Expanded detail (click any row):**
- The full conviction, risk, hold period
- Entry quality and strategy rating
- Bull case / bear case / thesis invalidation
- Price targets (entry, exit, stop)
- Upcoming events
- AI reasoning
- Today's news summary
- Ripple effects
- Full fundamentals (P/E, margins, beta, institutional ownership)
- Three scenarios with probabilities
- Past analyses history
- AI report

---

## Two Simulation Modes

### Autopilot
The AI manages a virtual $10,000 on your behalf, completely autonomously. Every night it evaluates each stock and makes its own buy/sell decisions. You watch and track how it performs over time — no decisions needed from you.

This is how you build trust in the AI before using it with real money.

### Co-Pilot
The AI makes a daily recommendation but waits for your approval before "acting." For each stock, you can:
- **Approve** — agree with the AI's suggestion
- **Skip** — pass on this one
- **Override** — make your own different call

All three outcomes are tracked. Over time you can compare: when you followed the AI, how did it go? When you overrode it, were you right?

---

## Financial Chatbot

The chatbot comes pre-loaded with everything from tonight's analysis — no need to paste in prices or explain your positions. Just ask:

- *"Should I add to my MSFT position?"* — AI knows your current exposure and tonight's analysis
- *"Why did SOXL drop today?"* — AI already read the news and ripple effects
- *"What's the risk if the Fed raises rates next week?"* — AI knows which of your stocks are rate-sensitive

The chat is web-search enabled — if you ask about something that happened today that isn't in tonight's analysis, it can look it up in real time.

---

*FinanceCompanion is not a licensed financial advisor. It is an AI tool to help you understand market signals and make more informed decisions. Always do your own research before investing real money.*
