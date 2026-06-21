# FinanceCompanion — Data Sources & Pipeline

> Living document. Update this whenever a new data source or agent is added.

---

## Overview

Every night (11 PM CT, Mon–Fri), FinanceCompanion runs a 6-agent pipeline for each ticker in any user's watchlist. All agents run on GitHub Actions — not on your local machine or Railway. The pipeline produces one analysis record per ticker per day, shared across all users.

```
GitHub Actions (nightly)
└── For each ticker (in parallel):
    ├── [1] Price Agent       → market prices + technicals
    ├── [2] News Agent        → headlines → AI summary
    ├── [3] Event Agent       → earnings dates + Fed calendar
    ├── [4] Analyst Agent     → Wall Street consensus + price targets
    │
    │   (all 4 run simultaneously)
    │
    ├── [5] Ripple Agent      → 2nd/3rd order effects (Sonnet)
    └── [6] Verdict Agent     → final BUY/HOLD/SELL/WATCH (Sonnet)
```

---

## Agent 1 — Price Agent

**What it fetches:** Every price and technical indicator needed to assess where the stock is right now.

**Primary source: yfinance**
- yfinance is a Python library that pulls data from Yahoo Finance's internal APIs
- It is NOT web scraping — it calls Yahoo's undocumented JSON endpoints directly
- No API key required; subject to rate limiting (we pre-fetch once and share across all agents to avoid this)

**Secondary source: Finnhub**
- Finnhub is a paid financial data API (free tier available)
- Used only for cross-validation of the current price
- If yfinance and Finnhub disagree by more than 2%, a conflict note is flagged

**Data points fetched:**

| Data Point | Source | Frequency |
|---|---|---|
| Current price | yfinance (real-time delayed ~15 min) | Daily |
| Previous close | yfinance | Daily |
| Today's % change | Computed: `(current - prev_close) / prev_close` | Daily |
| Today's high | yfinance | Daily |
| Today's low | yfinance | Daily |
| 52-week high | yfinance | Daily (rolling 1-year window) |
| 52-week low | yfinance | Daily (rolling 1-year window) |
| 52-week range position | Computed: where current price sits between 52w low and high (0–100%) | Daily |
| Volume (today) | yfinance | Daily |
| Average volume (3-month) | yfinance | Daily |
| 50-day moving average (MA50) | yfinance pre-computed field | Daily |
| 200-day moving average (MA200) | yfinance pre-computed field | Daily |
| RSI (14-day) | Computed in-house from 1 year of daily close prices using `pandas-ta` | Daily |
| Price cross-validation | Finnhub real-time quote | Daily |

**How the history is used:**
- We pull 1 full year of daily closing prices (`t.history(period="1y")`) — that's ~252 trading days
- From that history we compute RSI ourselves (not taken from any external source)
- MA50 and MA200 are taken directly from Yahoo Finance's pre-computed fields, not recomputed

---

## Agent 2 — News Agent

**What it fetches:** Recent headlines about the company, then summarizes them using AI.

**How we get news — NOT web scraping:**

| Source | How it works | Volume |
|---|---|---|
| yfinance news feed | Yahoo Finance serves a JSON list of recent article titles and publishers attached to each ticker. No scraping — it's a structured API response. | Up to 8 headlines |
| Finnhub company news | Finnhub's `/company-news` endpoint returns structured JSON with headline, source, and timestamp. Covers the last 7 days. | Up to 8 headlines |

**Deduplication:** Headlines from both sources are merged and deduplicated (first 60 characters compared) to avoid the same story appearing twice. Up to 12 unique headlines are kept.

**AI summarization:**
- The raw headlines are sent to **Claude Haiku** (fast, cheap model)
- Haiku writes a 3–4 sentence summary: what happened, sentiment (positive/negative/neutral), and any specific catalysts
- This summary is what you see in the "News Summary" section of the dashboard

**What we do NOT have:**
- Full article text (only headlines + publisher)
- Real-time news (Finnhub free tier has a delay; yfinance is near-real-time)
- Earnings call transcripts
- SEC filings

---

## Agent 3 — Event Agent

**What it fetches:** Upcoming dates that could move the stock.

| Event Type | Source | Lookahead |
|---|---|---|
| Earnings date | yfinance calendar (primary) | Next scheduled date |
| Earnings date (cross-check) | Finnhub earnings calendar | Next 90 days |
| Fed rate decisions (FOMC) | Hardcoded 2026 FOMC schedule | Next 2 meetings |

**Logic:** yfinance earnings date is preferred. If missing, Finnhub fills in. If both agree, no conflict. FOMC dates are hardcoded annually and need to be updated each year.

**How earnings dates affect the Verdict:**
- Earnings within 5 calendar days → `is_important_day = true`
- Leveraged ETFs (SOXL, MVLL, etc.) → **never hold through earnings** regardless of verdict

---

## Agent 4 — Analyst Agent

**What it fetches:** What Wall Street analysts collectively think about the stock.

**Primary source: yfinance**

| Data Point | What it means |
|---|---|
| Analyst consensus | Aggregated recommendation: STRONG BUY / BUY / HOLD / SELL / STRONG SELL |
| Number of analysts | How many analysts cover this stock |
| Mean price target | Average of all analyst 12-month price targets |
| High price target | Most bullish analyst target |
| Low price target | Most bearish analyst target |
| Upside % | `(mean_target - current_price) / current_price × 100` |

**Secondary source: Finnhub**
- Finnhub returns raw vote counts (strongBuy, buy, hold, sell, strongSell) from the most recent analyst survey
- We convert to BUY/HOLD/SELL using a 60% majority rule
- If yfinance and Finnhub disagree on consensus direction, a conflict note is flagged

---

## Agent 5 — Ripple Agent

**What it does:** Takes today's news and asks: what happens next? Who else gets affected?

- Model: **Claude Sonnet** (most capable)
- Input: ticker, news summary, sector
- Output: 2–3 paragraphs on 2nd and 3rd order effects
- Examples: "If NFLX recovers, Disney+ feels pressure to cut prices" or "SOXL near ATH means any semis correction hits it 3x harder"

This is pure AI reasoning — no external data source.

---

## Agent 6 — Verdict Agent

**What it does:** Synthesizes all 4 data agents + ripple analysis + historical context → issues the final verdict.

- Model: **Claude Sonnet**
- Input: everything from agents 1–5 + last 5 days of prior verdicts + stock memory (prose narrative of prior analyses)
- Output: verdict (BUY/HOLD/SELL/WATCH), entry price, take-profit price, stop loss, hold period, reasoning

**Key rules baked into the prompt:**
- If signals conflict or are weak → issue WATCH (no advice is better than wrong advice)
- Leveraged ETFs (any ticker with 2X/3X/L/Ultra in the name) → max hold 1–3 days, never buy after a 15%+ single-day run, always set a tight stop loss
- If verdict reverses from prior history → flag `is_important_day = true`
- Earnings within 5 days → flag `is_important_day = true`

---

## Data Flow Summary

```
yfinance ──────────────────────────────────────────────┐
  • 1 year daily OHLCV prices                          │
  • Current price, volume, 52w range                   ├──► Price Agent ──► PriceData
  • Pre-computed MA50, MA200                            │
  • Analyst consensus + price targets                  ├──► Analyst Agent ──► AnalystData
  • News headlines (up to 8)                           ├──► News Agent ──► news summary
  • Earnings calendar                                  ├──► Event Agent ──► events list
                                                       │
Finnhub ────────────────────────────────────────────────┤
  • Real-time quote (cross-validation only)            ├──► Price Agent (conflict check)
  • Analyst vote counts (cross-validation)             ├──► Analyst Agent (conflict check)
  • 7-day company news (merged with yfinance)          ├──► News Agent (merged headlines)
  • Earnings calendar (fallback)                       └──► Event Agent (fallback)

Claude Haiku ──────────────────────────────────────────► Summarize news headlines

Claude Sonnet ─────────────────────────────────────────► Ripple Agent
                                                       ► Verdict Agent (final call)

Railway PostgreSQL ─────────────────────────────────────► Persisted as StockAnalysis row
                                                          (one per ticker per day)
```

---

## Data Caching — How We Avoid Re-Fetching

Raw market data is expensive (rate limits) and Yahoo Finance will block IPs that make too many requests. To prevent redundant fetches when the pipeline runs more than once in a day:

**DB cache table: `market_data_cache`**

| Column | What's stored |
|---|---|
| `ticker` | e.g. "NFLX" |
| `cache_date` | today's date (primary key with ticker) |
| `info_json` | Full yfinance `.info` dict — prices, fundamentals, analyst targets |
| `history_json` | 1 year of daily OHLCV prices as JSON |
| `news_json` | Raw news headline list |
| `calendar_json` | Earnings calendar |

**How it works:**
1. Before calling yfinance, `yf_fetcher.py` checks if a row exists for `(ticker, today)` in `market_data_cache`
2. If found → deserialize and return immediately. **No API call made.**
3. If not found → fetch from yfinance → save to DB → return data
4. All 4 agents (Price, News, Event, Analyst) share the same cached `YFData` object within a single run

**GitHub Actions deduplication:**
- Before fetching any data, the nightly agent calls `GET /jobs/admin/analyzed-today`
- Any ticker already in the response is skipped entirely — no fetch, no POST
- This means if you trigger the nightly job twice in one day, the second run is a no-op for already-done tickers

**Cache lifetime:** One calendar day. Each day starts fresh — the next run always fetches new data.

---

---

## TODO — Data & Analysis Improvements

Items marked 🟢 are free/low-effort using data we already fetch. Items marked 🔵 require a new source or API.

### Phase 1 — Use data we already have (yfinance `.info` is already downloaded, just unused)

- [ ] 🟢 **Fundamentals**: extract P/E (trailing + forward), EPS (trailing + forward), revenue growth, earnings growth, debt-to-equity, gross/operating/net profit margins, free cash flow, return on equity — all in `yf_data.info` today
- [ ] 🟢 **Short interest**: `shortPercentOfFloat`, `shortRatio` — already in `yf_data.info`. Flag high short interest on BUY calls as a risk.
- [ ] 🟢 **Institutional ownership**: `heldPercentInstitutions`, `heldPercentInsiders` — already in `yf_data.info`. Institutions exiting quietly is a bearish signal.
- [ ] 🟢 **Beta**: `beta` field in `yf_data.info`. Tells users how volatile this stock is relative to the market.
- [ ] 🟢 **Dividend yield**: `dividendYield`, `trailingAnnualDividendYield` — relevant for income-focused users.
- [ ] 🟢 **MACD**: computable from existing 1-year price history using `pandas-ta`. Trend momentum signal.
- [ ] 🟢 **Bollinger Bands**: computable from existing 1-year price history. Flags unusually stretched price moves.
- [ ] 🟢 **Volume trend**: compare today's volume vs. 3-month average — already have both, just not passing to verdict agent as a signal.

### Phase 2 — New lightweight data sources

- [ ] 🔵 **Sector relative strength**: pull sector ETF (e.g. XLK for tech, XLE for energy) alongside each ticker and compare 1-month returns. Answers "is this stock beating or lagging its sector?"
- [ ] 🔵 **S&P 500 relative strength**: pull SPY price alongside each ticker. A stock "doing well" in a rising market is different from one beating the market.
- [ ] 🔵 **Insider trading trend**: SEC EDGAR Form 4 filings (free API). Track pattern of insider buys/sells over last 90 days — not just single events.
- [ ] 🔵 **Earnings surprise history**: how has this stock reacted to its last 4 earnings reports? Beat/miss + stock reaction. yfinance may have partial data; SEC EDGAR for full history.

### Phase 3 — Richer sources (evaluate when Phase 1+2 are done)

- [ ] 🔵 **Full article text for news**: headline-only summarization misses context. Paid news APIs (Benzinga, Dow Jones) or RSS scraping of financial sites.
- [ ] 🔵 **Options flow / unusual activity**: large options bets signal institutional conviction. Sources: Unusual Whales (paid), Market Chameleon (partial free).
- [ ] 🔵 **Short squeeze scoring**: combine short interest % + days-to-cover + recent price momentum to score squeeze potential. Data from Finra (free, weekly) or Ortex (paid).
- [ ] 🔵 **13F institutional holdings**: what major funds added/removed each quarter. SEC EDGAR (free, quarterly lag).
- [ ] 🔵 **Macro indicators**: CPI, unemployment, Fed funds rate trend — context for whether the broader environment is risk-on or risk-off. FRED API (free).
- [ ] 🔵 **Intraday candlestick data**: 5-min/15-min OHLCV for pattern recognition. Only relevant if we ever move toward day-trade signals. Polygon.io or Alpha Vantage (free tier limited).

### Not planned (out of scope for this app's audience)

- Social sentiment (Reddit/X) — too noisy, misleading for working-class investors
- HFT / order flow data — institutional-grade, not applicable
- Crypto — out of scope for now

---

See [YFINANCE_FIELD_AUDIT.md](YFINANCE_FIELD_AUDIT.md) for a full field-by-field audit of everything yfinance returns vs. what we currently use.

*Last updated: 2026-06-21*
