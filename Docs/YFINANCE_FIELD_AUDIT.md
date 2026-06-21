# yfinance Field Audit — What We Fetch vs. What We Use

> Living document. Every field yfinance returns is listed here.
> ✅ = currently extracted and used | 💾 = fetched and cached (raw JSON) but not extracted | ❌ = not fetched at all

---

## How yfinance data enters our system

`yf_fetcher.py` calls 4 things per ticker:
- `t.info` — the big dict (~100-150 fields)
- `t.history(period="1y")` — 1 year of daily OHLCV
- `t.news` — recent headlines list
- `t.calendar` — earnings date + estimate

**The good news:** our `market_data_cache` table saves ALL four as raw JSON blobs.
So every field listed below as 💾 is already preserved in the DB — we just haven't extracted it into analysis columns yet.

**The gap:** several yfinance endpoints we never call at all (marked ❌).

---

## Part 1 — `t.info` fields

### Price & Market Data

| Field | Status | Value |
|---|---|---|
| `currentPrice` / `regularMarketPrice` | ✅ | Used as main price |
| `previousClose` / `regularMarketPreviousClose` | ✅ | Used for day change % |
| `open` / `regularMarketOpen` | 💾 | Cached, not extracted |
| `dayHigh` / `regularMarketDayHigh` | ✅ | Used |
| `dayLow` / `regularMarketDayLow` | ✅ | Used |
| `volume` / `regularMarketVolume` | ✅ | Used |
| `averageVolume` | ✅ | Used (3-month avg) |
| `averageVolume10days` / `averageDailyVolume10Day` | 💾 | Short-term volume avg — useful for spike detection |
| `fiftyTwoWeekHigh` | ✅ | Used |
| `fiftyTwoWeekLow` | ✅ | Used |
| `fiftyTwoWeekChange` | 💾 | 1-year % return — important performance context |
| `SandP52WeekChange` | 💾 | **Stock vs. S&P 500 over 1 year — relative strength signal** |
| `fiftyDayAverage` | ✅ | Used as MA50 |
| `twoHundredDayAverage` | ✅ | Used as MA200 |
| `marketCap` | 💾 | Company size — large/mid/small cap matters for risk |
| `beta` | 💾 | **Volatility vs. market — critical risk metric** |
| `bid` / `ask` / `bidSize` / `askSize` | 💾 | Spread — low priority |
| `currency` | 💾 | Needed for non-USD tickers |
| `exchange` / `exchangeName` | 💾 | Context for international tickers |
| `quoteType` | 💾 | EQUITY vs ETF vs MUTUALFUND |
| `shortName` / `longName` | 💾 | Company display name |

### Valuation

| Field | Status | Value |
|---|---|---|
| `trailingPE` | 💾 | **P/E ratio (trailing 12 months) — is it cheap or expensive?** |
| `forwardPE` | 💾 | **Forward P/E — what market expects** |
| `priceToBook` | 💾 | P/B ratio — asset value context |
| `priceToSalesTrailing12Months` | 💾 | P/S ratio |
| `enterpriseValue` | 💾 | Total company value inc. debt |
| `enterpriseToRevenue` | 💾 | EV/Revenue multiple |
| `enterpriseToEbitda` | 💾 | EV/EBITDA — cleaner than P/E for leveraged companies |
| `trailingPegRatio` / `pegRatio` | 💾 | P/E relative to growth rate — growth at reasonable price |
| `bookValue` | 💾 | Net asset value per share |
| `trailingEps` | 💾 | **Actual EPS last 12 months** |
| `forwardEps` | 💾 | **Estimated EPS next 12 months** |

### Growth & Profitability

| Field | Status | Value |
|---|---|---|
| `revenueGrowth` | 💾 | **YoY revenue growth — is the business growing?** |
| `earningsGrowth` | 💾 | **YoY earnings growth** |
| `grossMargins` | 💾 | % revenue left after COGS |
| `operatingMargins` | 💾 | % revenue after operating costs |
| `profitMargins` | 💾 | **Net profit margin — bottom line efficiency** |
| `ebitdaMargins` | 💾 | EBITDA as % of revenue |
| `totalRevenue` | 💾 | Annual revenue |
| `grossProfits` | 💾 | Gross profit dollars |
| `ebitda` | 💾 | Earnings before interest/taxes/depreciation |

### Financial Health

| Field | Status | Value |
|---|---|---|
| `totalDebt` | 💾 | **Total debt — balance sheet risk** |
| `totalCash` | 💾 | Cash on hand |
| `totalCashPerShare` | 💾 | Cash per share |
| `debtToEquity` | 💾 | **Leverage ratio — high = risky** |
| `currentRatio` | 💾 | Short-term liquidity (current assets / current liabilities) |
| `quickRatio` | 💾 | Stricter liquidity test |
| `operatingCashflow` | 💾 | **Cash from operations — real earnings quality check** |
| `freeCashflow` | 💾 | **Cash left after capex — fuels buybacks/dividends** |
| `returnOnAssets` | 💾 | How efficiently assets generate profit |
| `returnOnEquity` | 💾 | **How efficiently equity generates profit** |

### Short Interest & Ownership

| Field | Status | Value |
|---|---|---|
| `shortPercentOfFloat` | 💾 | **% of float sold short — squeeze potential / bearish signal** |
| `shortRatio` | 💾 | **Days to cover — how long to unwind all shorts** |
| `sharesShort` | 💾 | Raw short share count |
| `sharesShortPriorMonth` | 💾 | Month-over-month short change |
| `sharesShortPreviousMonthDate` | 💾 | Date of prior reading |
| `heldPercentInstitutions` | 💾 | **% held by institutions — smart money signal** |
| `heldPercentInsiders` | 💾 | **% held by insiders — alignment signal** |
| `sharesOutstanding` | 💾 | Total shares |
| `floatShares` | 💾 | Tradeable shares |
| `impliedSharesOutstanding` | 💾 | Includes options/warrants |

### Analyst Data

| Field | Status | Value |
|---|---|---|
| `recommendationKey` | ✅ | Used (buy/hold/sell) |
| `recommendationMean` | 💾 | Numeric score (1=Strong Buy, 5=Sell) |
| `numberOfAnalystOpinions` | ✅ | Used |
| `targetHighPrice` | ✅ | Used |
| `targetLowPrice` | ✅ | Used |
| `targetMeanPrice` | ✅ | Used |
| `targetMedianPrice` | 💾 | Median (less skewed than mean) |

### Dividends

| Field | Status | Value |
|---|---|---|
| `dividendRate` | 💾 | Annual dividend per share |
| `dividendYield` | 💾 | **Dividend yield % — important for income investors** |
| `exDividendDate` | 💾 | Next ex-dividend date — event that moves price |
| `payoutRatio` | 💾 | % of earnings paid as dividends |
| `fiveYearAvgDividendYield` | 💾 | Historical yield context |
| `lastDividendValue` | 💾 | Most recent dividend payment |
| `trailingAnnualDividendYield` | 💾 | Last 12 months yield |

### Company Info

| Field | Status | Value |
|---|---|---|
| `sector` | 💾 | e.g. Technology, Healthcare |
| `industry` | 💾 | e.g. Software—Infrastructure |
| `fullTimeEmployees` | 💾 | Headcount |
| `longBusinessSummary` | 💾 | **Plain-English company description — great for chat context** |
| `website` | 💾 | Company URL |
| `country` | 💾 | Jurisdiction risk |

### Corporate Actions

| Field | Status | Value |
|---|---|---|
| `lastSplitFactor` | 💾 | e.g. "2:1" |
| `lastSplitDate` | 💾 | Date of last split |

---

## Part 2 — `t.history(period="1y")` columns

DataFrame with 252 rows (1 trading year), one per day.

| Column | Status | Notes |
|---|---|---|
| `Open` | 💾 | Cached, not used |
| `High` | 💾 | Cached, not used — needed for candlestick patterns |
| `Low` | 💾 | Cached, not used — needed for candlestick patterns |
| `Close` | ✅ | Used — RSI computed from this |
| `Volume` | 💾 | Cached, not extracted — volume trend computable from this |
| `Dividends` | 💾 | Dividend events in history |
| `Stock Splits` | 💾 | Split events in history |

**Computable from history but not yet computed:**
- MACD (from Close prices)
- Bollinger Bands (from Close prices)
- ATR / Average True Range (from High, Low, Close)
- Daily volume vs. average (volume spike detection)
- Candlestick patterns (from Open, High, Low, Close)

---

## Part 3 — `t.news`

List of dicts per article.

| Field | Status | Notes |
|---|---|---|
| `title` | ✅ | Used in news summary |
| `publisher` | ✅ | Used |
| `providerPublishTime` | ✅ | Used |
| `link` | 💾 | Article URL — not surfaced in UI yet |
| `thumbnail` | 💾 | Image URL — not used |
| `relatedTickers` | 💾 | Other tickers mentioned — useful for ripple analysis |
| `type` | 💾 | "STORY" vs "VIDEO" etc. |
| `uuid` | 💾 | Deduplication key |

---

## Part 4 — `t.calendar`

Dict with earnings estimate data.

| Field | Status | Notes |
|---|---|---|
| `Earnings Date` | ✅ | Used |
| `Earnings High` | 💾 | Analyst EPS estimate — high end |
| `Earnings Low` | 💾 | Analyst EPS estimate — low end |
| `Earnings Average` | 💾 | **Consensus EPS estimate — what market expects** |
| `Revenue High` | 💾 | Revenue estimate high |
| `Revenue Low` | 💾 | Revenue estimate low |
| `Revenue Average` | 💾 | **Consensus revenue estimate** |

---

## Part 5 — yfinance endpoints we never call (❌)

These require additional `t.*` calls — not currently in `yf_fetcher.py`.

| Endpoint | What it returns | Priority |
|---|---|---|
| `t.fast_info` | Lightweight real-time price snapshot (faster than `.info`) | Low |
| `t.balance_sheet` | Annual balance sheet (assets, liabilities, equity) | Medium |
| `t.quarterly_balance_sheet` | Quarterly balance sheet | Medium |
| `t.income_stmt` | Annual P&L (revenue, COGS, gross profit, net income) | Medium |
| `t.quarterly_income_stmt` | Quarterly P&L — trend is more useful than annual | High |
| `t.cash_flow` | Annual cash flow statement | Medium |
| `t.quarterly_cash_flow` | Quarterly cash flow | Medium |
| `t.earnings_dates` | Historical earnings dates + EPS estimate vs actual | **High — shows beat/miss history** |
| `t.upgrades_downgrades` | Analyst upgrade/downgrade history with firms | High |
| `t.institutional_holders` | Top 10 institutional holders | Medium |
| `t.major_holders` | Insider %, institution %, float % breakdown | Medium |
| `t.insider_transactions` | Recent insider buy/sell transactions | High |
| `t.analyst_price_targets` | Detailed analyst price target history | Medium |
| `t.eps_trend` | How EPS estimates have moved over time | High |
| `t.eps_revisions` | Upward/downward EPS revisions — analyst conviction signal | High |
| `t.revenue_estimate` | Forward revenue estimates by quarter/year | Medium |
| `t.earnings_estimate` | Forward EPS estimates by quarter/year | High |
| `t.sustainability` | ESG scores | Low |
| `t.recommendations` | Full recommendation history | Medium |

---

## Summary

| Category | Fields in `.info` | Currently Used | Cached (raw) | Not Fetched |
|---|---|---|---|---|
| Price & Market | ~20 | 9 | 11 | 0 |
| Valuation | ~12 | 0 | 12 | 0 |
| Growth & Profitability | ~9 | 0 | 9 | 0 |
| Financial Health | ~10 | 0 | 10 | 0 |
| Short Interest & Ownership | ~9 | 0 | 9 | 0 |
| Analyst Data | ~7 | 4 | 3 | 0 |
| Dividends | ~7 | 0 | 7 | 0 |
| Company Info | ~6 | 0 | 6 | 0 |
| History columns | 7 | 1 | 6 | 0 |
| News fields | 8 | 3 | 5 | 0 |
| Calendar fields | 7 | 1 | 6 | 0 |
| Additional endpoints | ~17 | 0 | 0 | **17** |

**Key takeaway:** We're already caching almost everything from `.info`, history, news, and calendar. The main gap is the 17 additional endpoints we never call at all — especially `earnings_dates` (beat/miss history), `upgrades_downgrades`, `insider_transactions`, `eps_revisions`, and quarterly financials.

---

## TODO — Extraction & New Endpoints

- [ ] 🟢 Extract `beta`, `shortPercentOfFloat`, `shortRatio`, `heldPercentInstitutions`, `heldPercentInsiders` from cached `.info` and pass to Verdict Agent
- [ ] 🟢 Extract `trailingPE`, `forwardPE`, `revenueGrowth`, `profitMargins`, `debtToEquity`, `freeCashflow`, `returnOnEquity` from cached `.info`
- [ ] 🟢 Extract `SandP52WeekChange` from cached `.info` — free relative strength vs S&P 500
- [ ] 🟢 Extract `dividendYield`, `exDividendDate` — relevant event for income investors
- [ ] 🟢 Extract `longBusinessSummary` — feed to chat for company context
- [ ] 🟢 Extract `sector`, `industry` from cached `.info` — already in watchlist model but not from yfinance
- [ ] 🟢 Compute MACD, Bollinger Bands, volume trend from cached history
- [ ] 🔵 Add `t.earnings_dates` fetch — beat/miss history is high signal
- [ ] 🔵 Add `t.upgrades_downgrades` — analyst conviction trend
- [ ] 🔵 Add `t.insider_transactions` — insider buy/sell pattern
- [ ] 🔵 Add `t.eps_revisions` — are analysts raising or cutting estimates?
- [ ] 🔵 Add `t.quarterly_income_stmt` — revenue/earnings trend over 4 quarters

*Last updated: 2026-06-21*
