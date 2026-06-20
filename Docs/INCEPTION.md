# FinanceCompanion — Inception Document

> A living document. Updated as ideas evolve, decisions are made, and the product takes shape.

---

## The Problem

Most working people want to grow their money through stocks, but they don't have time to follow the market. They're not financial experts — they're busy professionals managing careers, families, and life. They can't spend hours reading earnings reports or watching CNBC. And they can't afford a personal financial advisor.

So they either:
- Do nothing and feel guilty about it
- Make random bets based on news they half-heard
- Get overwhelmed and give up

There's no one in their corner saying: *"Hey, here's what you should do right now — and here's why."*

---

## The Vision

**FinanceCompanion** is an AI-powered stock advisor built for the working class — busy people who want to grow their money without becoming finance experts.

Think of it like having a close friend who happens to be brilliant at finance. This friend doesn't confuse you with jargon. They just tell you what they think, confidently, based on real data. You trust them because they've always been straight with you.

That's the tone. That's the relationship we're building.

---

## Who It's For

**Primary user:** A working professional — could be in tech, healthcare, education, any field — who:
- Has some money to invest but not a lot of time
- Already uses or is thinking about Robinhood
- Wants clear guidance, not charts and noise
- Gets frustrated with financial apps that give data but no direction
- Is nervous about making mistakes with real money

**This is not for:** Day traders, finance professionals, or anyone who already has the time and knowledge to manage their own portfolio.

---

## Core Philosophy

1. **Be the advisor, not the dashboard.** Don't just show data — give a verdict. "Now is a good time to buy" beats "the RSI is at 42."
2. **Build trust through transparency.** Show the AI's reasoning. Show its track record. Let users see if it's actually right before they follow it with real money.
3. **Zero hallucination policy.** Every recommendation must be grounded in real market data. The AI should say "I don't know" before it guesses.
4. **Start safe, earn trust.** Before users act on real money, let them run the AI in simulation mode and see the results.

---

## The Two Modes

Two ways to interact with the same set of stocks:

### 1. Autopilot
- AI runs a 6-month forward simulation with $10,000 virtual money
- Runs in **real time** — AI evaluates each day's market data as it arrives and makes decisions day by day. No backtesting, no looking at future data.
- AI decides everything: when to enter, when to exit, when to hold
- User just watches and tracks how the AI performs

### 2. Co-pilot
- AI makes daily recommendations with specific entry/exit targets and reasoning
- User can **approve the AI's suggestion**, **skip it**, or **make their own manual move** entirely
- All three outcomes are tracked — approved, skipped, and overridden
- Over time the data shows: when did you follow the AI, when did you go your own way, and who was right?

**Why this works:** Users don't trust the AI blindly on day one. They watch Autopilot prove itself on virtual money, while Co-pilot keeps them in full control. Trust is earned, not assumed.

---

## Feature Roadmap

Three areas, built in phases:

| Phase | Feature Area | What It Does |
|---|---|---|
| 1 | **Stock Simulation + Daily Digest** | AI tracks a watchlist, paper-trades virtual money in real time, delivers a daily verdict every evening |
| 2 | **Portfolio Advisor** | User enters real holdings; AI advises on timing, concentration, when to hold vs. sell |
| 3 | **Stock Discovery** | AI surfaces new stocks worth watching based on ripple analysis and market signals |

---

## Where We Start — Seed Stock Universe

**Industry focus: Semiconductors** — highly reactive to news, familiar territory, good swing potential.

### The ETF-First Approach

Start with a semiconductor ETF as the anchor, not individual stock picks. If one underlying company tanks, the ETF absorbs the hit. Then layer in individual stocks and the leveraged version for higher risk/reward.

| Ticker | What It Is | Risk Level |
|---|---|---|
| SOXQ | Semiconductor ETF (non-leveraged) | Medium |
| SOXL | Semiconductor ETF (leveraged, 3x the SOX index) | High |
| MRVL | Marvell Technology (individual stock) | Medium |
| MVLL | GraniteShares 2x MRVL (leveraged ETF) | Very High |
| NFLX | Netflix — test case for analyzing a falling large-cap | Medium |

**Stock metadata model:** For each ETF we track, maintain a table of its ~50 underlying companies. Watch the ETF, its top individual movers, and the leveraged version as a separate high-risk layer.

### Why This Example Motivated the Whole Idea (June 2026)
MRVL (Marvell Technology) was confirmed to join the S&P 500 on June 22, 2026. The regular MRVL stock was up ~66% in the month leading up to it. The leveraged ETF (MVLL, 2x MRVL) magnified those gains further. Anyone who knew about this catalyst two weeks earlier had a clear opportunity.

Most working people missed it — not because they're not smart, but because they're busy. This is exactly the kind of event FinanceCompanion should surface *before* it's fully priced in.

### Industry Expansion Plan
- **Phase 1:** Semiconductors only — learn, tune, prove it works
- **Phase 2:** Utilities, then other sectors
- **Important:** What works for semiconductors will NOT work for utilities. Signals, event types, and volatility patterns differ by industry. Each sector needs its own tuning.

---

## Event Calendar — Catalyst Tracking

The AI doesn't just track price — it tracks **events that move price**, and alerts you before they happen.

### Types of events to monitor:
- **Macro:** Fed decisions (rate changes, leadership changes), inflation data
- **Geopolitical:** US-China trade meetings, tariff announcements, MOUs
- **Sector-specific:** Semiconductor export controls, chip manufacturing bills, trade restrictions
- **Company-specific:** Earnings announcements, analyst upgrades/downgrades, acquisitions, S&P 500 index additions
- **Leadership:** CEO public statements, major keynotes

### How it works:
AI alerts the user *before* the event, tied to their specific stocks:

> *"Wednesday: Fed decision on interest rates. Semiconductor stocks are historically sensitive to rate changes — watch your SOXQ and SOXL positions."*

> *"NVDA earnings coming up July 15. If you're holding SOXL, be aware — leveraged positions should not be held overnight through earnings."*

This is the feature that catches what you miss when you're buried in your day job.

---

## Daily Digest — What the User Receives

Every evening after market close, for each tracked stock. Concise, specific, no fluff.

```
MRVL — Marvell Technology
─────────────────────────
Current Price:     $313.00
52-Week Range:     $85.50 – $335.00
Today:             ▲ 2.3%  |  Volume: above average

Verdict:           HOLD — approaching resistance at $320
Entry Zone:        $290–$295 (if it pulls back Monday)
Exit Target:       $330 on S&P inclusion momentum
Analyst Consensus: Strong Buy (28 of 44 analysts)

Key Events Ahead:
  • June 22 — MRVL officially joins S&P 500 (pre-open)
  • July 15 — Earnings (reduce leveraged exposure before this)

AI Reasoning:
  S&P inclusion is now priced in at ~70%. There may be a
  "sell the news" dip Monday after open. Watch first 30
  minutes — if it holds $305, consider adding. If it
  drops below $295, that's the real entry.

Sources: [Yahoo Finance] [NASDAQ.com] [Benzinga]
```

**Format rules:**
- 10–15 lines max. No fluff.
- Always cite sources with links — user can dig deeper if they want, but doesn't have to.
- Specific numbers, not vague direction. Not "looks good" — "entry at $290, exit at $330."

---

## 52-Week Analysis — Core Entry/Exit Signal

The 52-week range is a primary signal for timing entries on stocks we already believe in:

- **Near 52-week low** → potential entry, especially for fundamentally strong companies
- **Near 52-week high** → caution, may be overextended
- **Middle of range** → context-dependent, look at trend direction

**Example:** MVLL at $193, with a 52-week low of $183 and high of $214. It's near the bottom of its range — reasonable entry territory. AI flags this with a specific price target.

**Cost averaging for regular (non-leveraged) stocks:**
For strong companies whose stock is falling, buy incrementally on the way down:
- e.g., buy at $77, more at $74, more at $70
- Average down only as long as the company's fundamentals haven't changed
- This works for large, established companies that will recover — not for struggling small-caps like Evolent (EVH)

---

## Leveraged ETF Special Rules

Leveraged ETFs behave differently from regular stocks due to **time decay** — value erodes in flat or sideways markets. The AI must apply different logic to these instruments:

| Rule | Why |
|---|---|
| Max hold: 1–3 days | Time decay destroys value if the stock doesn't move |
| Never hold through earnings | Volatility spikes punish leveraged positions |
| Don't buy after a huge run | e.g., avoid MVLL after a 163% one-month gain |
| In-and-out same day is ideal | Capture the swing, don't overstay |

**Example AI verdict for a leveraged position:**
> *"MVLL: Entry only if it dips to $187–$188 Monday morning. Hold max 1–2 days. Target exit $195–$200. Do not hold through earnings on July 15."*

---

## Signal Propagation — Ripple Analysis

One of the most powerful AI advantages: tracing **second and third-order effects** of major news events across sectors.

A human reads a headline and reacts to the obvious. The AI reads it and maps the chain — who benefits downstream, who gets hurt, and at what distance.

**Example:**
```
SpaceX space data center announcement
  → massive compute demand
    → GPU/chip demand surge (NVDA, AMD)
      → chip manufacturing capacity pressure (TSMC, ASML)
        → rare earth / commodity demand (copper, lithium suppliers)
          → energy demand for data centers (nuclear plays, grid stocks)
```

**Quality bar — the AI must understand context, not just map mechanically.**
Counter-example: space data centers do NOT drive cooling technology demand the same way terrestrial ones do — radiative cooling in vacuum is extremely efficient. A naive chain-trace would wrongly flag thermal management stocks as beneficiaries. The AI must understand the actual physics and economics at each link, or it produces confidently wrong advice — which is worse than no advice.

**How it connects to the product:**
- AI monitors major news daily (macro, sector, geopolitical)
- When a significant event hits, AI maps the ripple and cross-references the user's watchlist
- If the ripple touches a stock the user doesn't own, AI flags it as a discovery opportunity
- This is the primary engine behind **Phase 3 — Stock Discovery**

Works in both directions. Good news travels up the chain; bad news travels down.

---

## Financial Chatbot — In-App Q&A

The daily digest is the scheduled heavy analysis — every agent runs, data is cross-validated, verdict is issued. The chatbot is what happens after that. It's how the user goes deeper without starting over.

### The Core Problem It Solves
When you go to ChatGPT or Claude.ai and ask about a stock, you start from zero every time. You have to paste in price data, explain your position, describe what you already know, and re-establish all context. By the time you get a useful answer, you've spent 10 minutes just setting up the question.

FinanceCompanion's chatbot starts with everything already loaded. The user just asks.

### What "Already Loaded" Means
When the user opens the chat, the AI has in its context:
- Tonight's full analysis for every tracked stock (price, technicals, news, events, analyst consensus)
- Every verdict from the past 30 days — what the AI said and whether it was right
- The user's current simulation positions — what they hold, at what price, since when
- The user's Co-pilot history — which recommendations they approved, skipped, or overrode
- Upcoming events for their stocks — earnings, Fed dates, index changes
- The ripple analysis from tonight — which macro events are affecting which stocks

### What the User Can Do
Ask naturally, without setup:

> *"Should I get into MVLL Monday morning?"*
> → AI knows: current price, 52-week range, S&P inclusion event is Monday, leveraged hold rules, recent 163% run-up. Answers directly.

> *"Why did SOXQ drop today?"*
> → AI already pulled today's news and ran ripple analysis. It explains without the user having to provide any data.

> *"The AI said hold MRVL but I read something about their CEO. Does that change anything?"*
> → User brings new information. AI incorporates it against what it already knows and re-reasons. No re-running agents — just deeper thinking on existing context.

> *"Compare what the AI would have done vs what I actually did on MRVL this week."*
> → AI has the full Co-pilot history. It pulls it up and gives the comparison instantly.

### What It Does NOT Do
- It does not re-run the data agents (no fresh API calls to yfinance or Finnhub)
- It does not replace the nightly analysis — that is always the authoritative source
- It does not answer questions about stocks outside the tracked watchlist with the same depth — it will answer, but it will say "I don't have tonight's analysis for this one"

### How Context Persists
The chatbot memory is **persistent across sessions** — not just within one conversation. If the user asked about MRVL two days ago and the AI gave a specific reasoning, today's chat still has that. The user can say "you said MRVL would hold $305 — it didn't, what happened?" and the AI knows exactly what it said and why.

This is the difference between a static report and an actual advisor. The advisor remembers your history.

---

## Data Sources — Two-Source Cross-Validation

Every data point is pulled from **two independent sources** and cross-validated before it reaches the AI. This is non-negotiable for the zero-hallucination policy.

**Note:** Google Finance has no public API (Google shut it down years ago). Any tool claiming to use it is scraping, which is fragile and unreliable. We don't use it.

**Primary: Yahoo Finance via `yfinance`**
- Free, no API key needed, Python-native
- Gets: OHLCV, 52-week range, analyst consensus, earnings dates, ETF data

**Secondary: Finnhub**
- Free tier: 60 API calls/minute
- Gets: OHLCV, analyst ratings, earnings calendar, news headlines
- Fully independent from Yahoo — different data pipeline, different source

### Cross-Validation Logic (inside the Price Agent)

```
Pull same data point from yfinance AND Finnhub
  → Prices match within acceptable range? → proceed
  → Prices disagree significantly?        → flag it, note discrepancy, do not guess
```

Example: Yahoo says MRVL closed at $313.00, Finnhub says $312.80 → normal rounding, proceed.
Example: Yahoo says $313, Finnhub says $295 → something is wrong → agent flags it, does not issue a verdict until resolved.

Same logic applies to analyst consensus — if the two sources disagree on Buy vs. Hold, the Verdict Agent reasons through the conflict rather than blindly picking one.

| Data Type | Source 1 | Source 2 |
|---|---|---|
| Price / OHLCV / 52-week range | yfinance | Finnhub |
| Analyst ratings / consensus | yfinance | Finnhub |
| News & headlines | yfinance | Finnhub |
| Earnings calendar | yfinance | Finnhub |
| Technical indicators (RSI, MAs) | Computed from yfinance data | Computed from Finnhub data — compared |
| ETF constituents | ETF provider websites | Cross-checked manually (monthly) |
| Macro events (Fed calendar) | Fed website (public) | Cached, not dual-sourced |

---

## System Architecture

### What Kind of System Is This?
An AI-native financial intelligence platform with a simulation layer. Not a trading app, not a portfolio tracker — those just show you data. This one *thinks*, then *tells you what to do*.

### Agentic Multi-Agent Design

The AI layer is not a single Claude call. It is a **multi-agent pipeline** — specialized sub-agents each own one job, run in parallel, and a Verdict Agent synthesizes everything including catching contradictions between them.

```
Orchestrator Agent
├── Price Agent       → pulls OHLCV from yfinance + Finnhub, cross-validates, computes technicals
├── News Agent        → pulls headlines from yfinance + Finnhub, summarizes sentiment
├── Event Agent       → pulls earnings dates, Fed calendar, upcoming catalysts
├── Analyst Agent     → pulls consensus ratings from yfinance + Finnhub, flags disagreements
├── Ripple Agent      → analyzes 2nd/3rd order effects of today's macro news on watchlist
└── Verdict Agent     → receives all 5 outputs, synthesizes, catches contradictions, issues final verdict
```

**Why this matters:**
- Price, News, Event, Analyst, and Ripple agents all run in **parallel** — no waiting
- Each agent is a specialist with its own focused system prompt and tools
- The Verdict Agent actively looks for contradictions across agents before issuing a recommendation
- If one agent's data conflicts with another's, it reasons through it — it does not blindly merge

**Auto-correction example:**
- Price Agent says: "MRVL near 52-week low — potential entry"
- Analyst Agent says: "14 of 20 analysts rate it Strong Sell"
- → Verdict Agent flags the conflict, investigates why, adjusts or qualifies the verdict

**Source failure handling:**
- If yfinance fails → Price Agent falls back to Finnhub, logs the fallback
- If both fail → no verdict issued for that stock that day, user is notified

### Five System Layers

**1. Data Ingestion**
- Market data — OHLCV pulled from yfinance + Finnhub, cross-validated
- Technical indicators — RSI, moving averages computed from both sources and compared
- News & sentiment — headlines from yfinance + Finnhub
- Market context — S&P 500 (`^GSPC`) and SOX index (`^SOX`) tracked as additional tickers
- User watchlist — which stocks are being tracked and what positions the simulation holds

**2. AI Intelligence Engine (Multi-Agent)**
- Sub-agents: Price, News, Event, Analyst, Ripple (run in parallel)
- Verdict Agent: synthesizes all outputs, catches contradictions, issues final recommendation
- Portfolio Health Agent *(Phase 2)*: concentration risk, rebalancing suggestions

**3. Simulation Engine**
- Tracks a virtual $10,000 portfolio per mode (Autopilot and Co-pilot tracked separately)
- Records every AI decision and every user decision with timestamp and reasoning
- Calculates daily P&L, running totals, win/loss rate
- Runs forward in real time — no backtesting

**4. Two-Mode Framework**
- Autopilot — AI acts autonomously on virtual money
- Co-pilot — AI recommends; user can approve, skip, or make their own manual move

**5. User Interface**
- Daily Digest — evening feed with per-stock verdict, entry/exit targets, events ahead
- Stock Detail — per-stock view: current position, verdict history, reasoning, chart
- Signal Feed — ripple events and which stocks they affect
- Performance Dashboard — Autopilot vs. Co-pilot tracked over time
- Financial Chatbot — context-aware Q&A on any tracked stock

### End-to-End Flow

```
Market closes (4PM ET)
  → Orchestrator triggers all sub-agents in parallel
    → Price + News + Event + Analyst + Ripple agents run simultaneously
      → All outputs collected by Verdict Agent
        → Verdict Agent synthesizes, checks for contradictions, issues verdict
          → Verdicts + reasoning saved to database
            → Simulation Engine updates virtual portfolios
              → User opens app next morning
                → Sees Daily Digest: verdicts, events ahead, Co-pilot approvals waiting
```

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js |
| Backend / API | FastAPI |
| Scheduler (daily job) | Railway cron or APScheduler |
| AI Engine | Anthropic Claude API (multi-agent) |
| Market Data — Primary | yfinance (Yahoo Finance, free) |
| Market Data — Secondary | Finnhub (free tier, cross-validation) |
| Technical Indicators | pandas-ta (computed in-house from price data) |
| Database | PostgreSQL |
| Deployment | Vercel (frontend) + Railway (backend + scheduler) |

---

## Data & Integrations

**Phase 1 — No account connection needed:**
- User manually enters the stocks they want to watch
- Or exports a CSV from Robinhood (Chrome extension available)

**Future — Robinhood MCP:**
Robinhood launched an official MCP (Model Context Protocol) server on May 27, 2026:
- Read-only access to real portfolio positions, balances, and watchlists
- Order placement isolated to a separate "Agentic account" — real portfolio is never touched
- Claude (Anthropic) is a named supported integration

This opens the door to reading a user's real Robinhood holdings automatically when they're ready for it.

---

## Open Questions

- What market data API do we use? (Polygon.io vs Alpha Vantage vs Yahoo Finance)
- What signals define "entry point" and "exit point"? (Technical analysis, fundamentals, sentiment, or a combination?)
- How does the AI handle leveraged ETFs differently in Autopilot mode — does it apply the special hold rules automatically?
- Should users set a risk profile (conservative / moderate / aggressive) that shapes recommendations?
- What does the Co-pilot approval flow look like — mobile vs. desktop?
- How do we weight analyst consensus vs. technical signals vs. event catalysts in the final verdict?
- Does the chatbot memory persist across days, or reset per session?

---

## Status

- [x] Problem defined
- [x] Target user identified
- [x] Two modes finalized: Autopilot + Co-pilot (approve / skip / override)
- [x] Feature roadmap defined (3 phases)
- [x] Seed stock universe defined — semiconductor-first (SOXQ, SOXL, MRVL, MVLL, NFLX)
- [x] ETF-first investment strategy agreed upon
- [x] Event Calendar feature scoped
- [x] Daily Digest format defined
- [x] 52-week range as core entry/exit signal agreed upon
- [x] Leveraged ETF special rules defined (time decay, max hold, no earnings overnight)
- [x] Signal Propagation / Ripple Analysis scoped
- [x] Financial Chatbot scoped
- [x] Robinhood MCP integration researched
- [x] Data sources identified
- [x] Data strategy finalized — yfinance (primary) + Finnhub (secondary), cross-validated
- [x] Agentic multi-agent architecture defined (Price, News, Event, Analyst, Ripple, Verdict agents)
- [ ] Market data API selected
- [ ] Tech stack finalized
- [ ] Phase 1 scope locked
- [ ] First build started

---

*Last updated: June 2026*
