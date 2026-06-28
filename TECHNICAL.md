# TECHNICAL.md — FinanceCompanion

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (Next.js — Vercel)                                  │
│  Dashboard → Stock cards, watchlist, digest                  │
│  Chat → SSE stream, tool-use indicator, conversation list    │
│  Simulation → Portfolio P&L, trade history, co-pilot panel   │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS / SSE
┌────────────────────▼────────────────────────────────────────┐
│  FastAPI (Railway)                                           │
│  /auth, /watchlist, /analysis, /chat/stream, /jobs, /admin  │
└────────────────────┬────────────────────────────────────────┘
                     │ SQLAlchemy
┌────────────────────▼────────────────────────────────────────┐
│  PostgreSQL (Railway)                                        │
└─────────────────────────────────────────────────────────────┘

Nightly (Railway Cron → POST /jobs/nightly):
  For each ticker (all in parallel):
    Price Agent  ─┐
    News Agent   ─┤── asyncio.gather ──► Ripple Agent (Haiku)
    Event Agent  ─┤
    Analyst Agent─┘
          ↓
    _build_performance_retrospective()   ← factual, no LLM
          ↓
    Verdict Agent (Sonnet) ← receives all above + retrospective + StockMemory
          ↓
    persist StockAnalysis (with token cost)
          ↓
    maybe_update_stock_memory() (Haiku, fire-and-forget)
```

---

## Data Model

### `users`
| Column | Type | Notes |
|--------|------|-------|
| email | VARCHAR PK | Google email |
| tier | VARCHAR | `free` / `pro` |
| is_admin | BOOLEAN | |
| tokens_used | INTEGER | cumulative |
| token_limit | INTEGER | NULL = no limit |
| portfolio_size | FLOAT | user-provided portfolio value |

### `watchlist_items`
| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR PK | UUID |
| user_email | VARCHAR FK | |
| ticker | VARCHAR | e.g. `NFLX` |
| company_name | VARCHAR | |
| sector | VARCHAR | |
| is_leveraged | BOOLEAN | true for 2x/3x ETFs |
| added_at | DATETIME | |
| last_read_analysis_id | VARCHAR FK | tracks unread state |
| last_read_at | DATETIME | |

### `stock_analyses` ← global per ticker, one per day
| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR PK | UUID |
| ticker | VARCHAR | |
| analysis_date | DATE | one row per ticker per day |
| current_price | FLOAT | |
| prev_close | FLOAT | |
| day_change_pct | FLOAT | |
| week_52_high / low | FLOAT | |
| range_position_pct | FLOAT | 0=at 52w low, 100=at high |
| volume / avg_volume | BIGINT | |
| ma_50 / ma_200 | FLOAT | |
| rsi | FLOAT | 0–100 |
| support_20d / resistance_20d | FLOAT | 20-day swing levels |
| pivot_point / pivot_r1 / pivot_s1 | FLOAT | classic pivot levels |
| sp500_day_chg | FLOAT | S&P 500 % today |
| sector_etf | VARCHAR | e.g. "XLK" |
| sector_day_chg | FLOAT | sector ETF % today |
| relative_strength_1d | FLOAT | stock % - sector % |
| fh_price | FLOAT | Finnhub price for cross-validation |
| fh_analyst_consensus | VARCHAR | Finnhub analyst rating |
| data_conflicts | TEXT | flagged cross-validation issues |
| analyst_consensus | VARCHAR | BUY/HOLD/SELL/STRONG BUY |
| analyst_count | INTEGER | |
| target_price_mean / high / low | FLOAT | |
| pe_trailing / pe_forward | FLOAT | |
| revenue_growth / earnings_growth | FLOAT | YoY (0.12 = 12%) |
| profit_margin / return_on_equity | FLOAT | |
| debt_to_equity | FLOAT | |
| free_cashflow | FLOAT | |
| beta | FLOAT | |
| short_float_pct / short_ratio | FLOAT | |
| inst_ownership_pct / insider_ownership_pct | FLOAT | |
| sp500_52w_change / stock_52w_change | FLOAT | |
| dividend_yield / market_cap | FLOAT | |
| sector / industry | VARCHAR | |
| verdict | VARCHAR | BUY/HOLD/SELL/WATCH |
| entry_target / exit_target / stop_loss | FLOAT | |
| hold_period | VARCHAR | e.g. "2-4 weeks" |
| reasoning | TEXT | 2–3 sentence plain-English |
| conviction_score | INTEGER | 0–100 |
| risk_level | VARCHAR | LOW/MED/HIGH |
| confidence | VARCHAR | High/Medium/Low |
| bull_case / bear_case / thesis_invalidation | TEXT | one sentence each |
| entry_quality | VARCHAR | GREAT/FAIR/WAIT |
| hold_and_forget_rating | VARCHAR | HOLD_AND_FORGET/CHECK_MONTHLY/WATCH_CLOSELY |
| position_size_pct | VARCHAR | e.g. "5–8%" |
| scenario_bull / base / bear | TEXT | one sentence each |
| scenario_bull/base/bear_pct | FLOAT | expected % return |
| scenario_bull/base/bear_prob | INTEGER | probability (three sum to 100) |
| dont_panic_note | TEXT | populated when price dropped >15% since last BUY |
| signal_convergence_score | INTEGER | 0–7 independent signals |
| convergence_details | TEXT | JSON dict of which signals fired |
| news_summary | TEXT | Haiku 3–4 sentence summary |
| events_json | TEXT | JSON list of upcoming events |
| ripple_analysis | TEXT | Haiku 2nd/3rd order effects |
| is_important_day | BOOLEAN | flagged by Verdict Agent |
| importance_reason | TEXT | why |
| verdict_a / verdict_b | VARCHAR | dual-agent fields (reserved) |
| verdict_agreement | BOOLEAN | dual-agent fields (reserved) |
| tokens_input / tokens_output | INTEGER | Anthropic usage for this analysis |
| tokens_cache_read / tokens_cache_write | INTEGER | prompt cache usage |
| cost_usd | FLOAT | USD cost for this analysis |
| created_at | DATETIME | |

### `stock_memories` ← global per ticker
| Column | Type | Notes |
|--------|------|-------|
| ticker | VARCHAR PK | |
| memory_narrative | TEXT | prose, max 1200 chars; updated nightly + after report generation |
| last_updated | DATETIME | |
| update_count | INTEGER | |

### `stock_reports` ← on-demand, one per ticker per day
| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR PK | UUID |
| ticker | VARCHAR | |
| report_date | DATE | |
| content | TEXT | markdown — Sonnet synthesis of last 30 analyses |
| analyses_count | INTEGER | how many past analyses were fed in |
| created_at | DATETIME | |

### `market_data_cache`
| Column | Type | Notes |
|--------|------|-------|
| ticker | VARCHAR PK | |
| cache_date | DATE PK | |
| info_json / history_json / news_json / calendar_json | TEXT | raw yfinance data |
| created_at | DATETIME | |

### `simulation_portfolios`
| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR PK | UUID |
| user_email | VARCHAR FK | |
| mode | VARCHAR | `autopilot` / `copilot` |
| ticker | VARCHAR | |
| shares | FLOAT | |
| entry_price | FLOAT | |
| status | VARCHAR | `watch` / `open` / `closed` |
| virtual_cash | FLOAT | starts at 10000 |

### `copilot_decisions`
| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR PK | UUID |
| user_email | VARCHAR FK | |
| analysis_id | VARCHAR FK | |
| decision | VARCHAR | `approve` / `skip` / `override` |
| override_action | VARCHAR | BUY/SELL/HOLD if override |
| override_price | FLOAT | |
| decided_at | DATETIME | |

### `conversations` / `messages`
Standard chatbot schema with token tracking per message (`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`).

---

## API Endpoints

### Auth
| Method | Path | Notes |
|--------|------|-------|
| POST | `/auth/verify` | Verify Google id_token, upsert user |

### Watchlist
| Method | Path | Notes |
|--------|------|-------|
| GET | `/watchlist?id_token=` | All items for user |
| POST | `/watchlist?id_token=` | Add ticker |
| DELETE | `/watchlist/{ticker}?id_token=` | Remove ticker |
| PATCH | `/watchlist/{ticker}/mark-read?id_token=` | Mark analysis as read |

### Analysis
| Method | Path | Notes |
|--------|------|-------|
| GET | `/analysis/digest?id_token=` | Today's analysis + unread state for watchlist |
| GET | `/analysis/reports?id_token=&limit=7` | Last N nightly report summaries |
| GET | `/analysis/important?id_token=&days=30` | Important-day analyses across watchlist |
| GET | `/analysis/{ticker}/latest` | Most recent analysis for ticker |
| GET | `/analysis/{ticker}/history?days=30` | Last N analyses per ticker |
| GET | `/analysis/{ticker}/report?id_token=` | Most recent AI report (any date) |
| POST | `/analysis/{ticker}/report?id_token=` | Generate report (cached per day); triggers memory update in background |

### Chat / Streaming
| Method | Path | Notes |
|--------|------|-------|
| GET | `/conversations?id_token=` | List conversations |
| POST | `/conversations?id_token=` | Create conversation |
| GET | `/conversations/{id}?id_token=` | Conversation with messages |
| DELETE | `/conversations/{id}?id_token=` | Delete |
| POST | `/chat/stream` | SSE streaming endpoint |

### Simulation
| Method | Path | Notes |
|--------|------|-------|
| GET | `/simulation/portfolio?id_token=&mode=` | Portfolio for autopilot or copilot |
| GET | `/simulation/trades?id_token=&mode=` | Trade history |
| POST | `/simulation/copilot-decision` | Record approve/skip/override |

### Jobs (protected by JOB_SECRET)
| Method | Path | Notes |
|--------|------|-------|
| POST | `/jobs/nightly` | Trigger nightly analysis |
| GET | `/jobs/admin/tickers` | All watchlisted tickers (used by nightly GHA workflow) |

---

## Agent Pipeline

### Execution Order Per Ticker

```python
# 1. Fetch yfinance data (cached per day in market_data_cache)
yf = await fetch_yf_data(ticker, db)

# 2. All four data agents in parallel
price, news, events, analyst = await asyncio.gather(
    fetch_price_data(ticker, yf_data=yf),
    fetch_news(ticker, company_name, yf_data=yf),     # returns (summary, usage)
    fetch_events(ticker, prefetched=yf),
    fetch_analyst_data(ticker, prefetched=yf),
)

# 3. Ripple agent (Haiku)
ripple = await analyze_ripple(ticker, news, sector)   # returns (analysis, usage)

# 4. Fetch historical context
stock_mem = await get_stock_memory(ticker, db)
recent = last 5 StockAnalysis rows for ticker

# 5. Performance retrospective (pure math, no LLM)
perf_retro = _build_performance_retrospective(recent, price.current_price)

# 6. Verdict Agent (Sonnet)
verdict = await generate_verdict(..., performance_retrospective=perf_retro)  # returns (VerdictResult, usage)

# 7. Persist StockAnalysis with token costs
# 8. Fire-and-forget: maybe_update_stock_memory()
```

### Agent → Model Mapping

| Agent | Model | Reason |
|-------|-------|--------|
| Price, Event, Analyst | No LLM | Pure data fetch + math |
| News summary | Haiku 4.5 | Speed + cost |
| Ripple analysis | Haiku 4.5 | Cost (switched from Sonnet; quality acceptable) |
| Stock memory update | Haiku 4.5 | Speed + cost, fire-and-forget |
| Memory from report | Haiku 4.5 | Background task |
| Verdict Agent | Sonnet 4.6 | Synthesizes all signals — quality critical |
| Report generation | Sonnet 4.6 | Long-form synthesis — quality critical |
| Chatbot | Sonnet 4.6 | Primary user interface |
| Title generation | Haiku 4.5 | Fire-and-forget |

### Token Pricing (for cost tracking)

| Model | Input ($/M) | Output ($/M) | Cache Read ($/M) |
|-------|------------|-------------|-----------------|
| Sonnet 4.6 | $3.00 | $15.00 | $0.30 |
| Haiku 4.5 | $0.80 | $4.00 | $0.08 |

---

## Performance Retrospective

Built in `nightly_runner._build_performance_retrospective()` — pure math, no LLM call.

For each past analysis that had a BUY or SELL verdict with targets:
1. Compare entry_target vs what price actually was the next day
2. Check if direction was correct (BUY → price went up? SELL → price went down?)
3. Check if stop loss was triggered
4. Check if exit target was hit

Result is a text block injected into the Verdict Agent prompt before it issues today's verdict. This forces the agent to acknowledge its past accuracy and recalibrate.

---

## Smart Skip Logic

In `nightly_runner._is_quiet_stock()` — called before the LLM pipeline:

```python
def _is_quiet_stock(price_change_pct, recent_analyses, events) -> bool:
    if abs(price_change_pct) >= 2.0: return False          # significant price move
    if any event within 5 days: return False               # binary risk imminent
    if last 3 verdicts not all the same: return False      # trend is changing
    if yesterday was is_important_day: return False         # important context
    return True  # safe to skip
```

When skipped: yesterday's StockAnalysis is reused, `created_at` is not updated. The frontend shows "N days ago" age label so users always know the freshness.

---

## StockMemory Update Sources

Memory is updated in two places:

1. **Nightly** (`maybe_update_stock_memory`) — after each Verdict Agent run, Haiku decides if anything significant happened. If yes, it rewrites the prose narrative. If no, it returns `NO_UPDATE`.

2. **After report generation** (`update_memory_from_report`) — when a user generates an AI report, a background task runs Haiku to extract lessons from the "What the AI Got Wrong" section and appends them to StockMemory. These lessons appear in the next nightly Verdict Agent run.

---

## Prompt Architecture

### Chatbot
`build_system_prompt(user_email, db, conversation_ticker)` returns `(base_prompt, dynamic_context)`:

- **`base_prompt`** — static persona, rules, tone, quality guidelines. Marked with `cache_control: ephemeral` → cached for 5 minutes, reads at 0.1× input cost.
- **`dynamic_context`** — tonight's analysis for all watchlist stocks, stock memories, open positions, conversation ticker focus.

### Verdict Agent
System prompt uses `cache_control: ephemeral`. `max_tokens` is 2500 (was 32000 — output never came close to that). Uses assistant prefill `{"` to force JSON-only output.

---

## Cross-Validation Logic

For price data (yfinance vs Finnhub):
- Fetch both concurrently
- If `abs(price_a - price_b) / price_a > 0.02` → flag in `data_conflicts`
- yfinance is primary (more reliable OHLCV)
- Conflict is always surfaced in the analysis, never silently discarded

Same pattern for analyst consensus and earnings dates.

---

## Important Day Flagging

Verdict Agent sets `is_important_day: true` when any of the following apply:
- Verdict reversal from the previous day's verdict
- Earnings within 5 calendar days
- Major index inclusion/exclusion event
- Analyst rating upgrade/downgrade by major firm
- Significant catalyst in ripple analysis
- Don't-panic situation (price dropped >15% since last BUY)

---

## Signal Convergence Score

Computed deterministically before the Verdict Agent call — 7 independent signals:

| Signal | Condition |
|--------|-----------|
| `oversold_rsi` | RSI < 42 |
| `near_52w_low` | Range position < 35% |
| `analyst_upside_15pct` | Analyst upside > 15% |
| `no_binary_risk` | Days to earnings > 21 |
| `positive_fcf` | Free cash flow > 0 |
| `institutional_backing` | Institutional ownership > 40% |
| `price_stabilizing` | Current price > MA200 × 0.90 |

**Conviction floor rule: score < 5 → verdict MUST be WATCH.** This is enforced in the prompt — the agent cannot override it.

---

## Report Generation

`POST /analysis/{ticker}/report`:

1. Check for existing `StockReport` with `report_date == today` → return cached if exists
2. Fetch last 30 `StockAnalysis` rows for ticker
3. Format each as compact text (date, verdict, price, conviction, reasoning, bull/bear, targets, scenarios)
4. Call Sonnet 4.6 with report prompt (6 sections: verdict trajectory, conviction trend, price target accuracy, recurring themes, right vs wrong, watch for)
5. Save to `stock_reports` table
6. Background task: `update_memory_from_report()` — Haiku extracts lessons and appends to StockMemory

**GET /analysis/{ticker}/report** returns the most recent report for any date (not just today). Frontend shows STALE badge + Regenerate button when not from today.

---

## Leveraged ETF Rules (enforced by Verdict Agent)

1. Max hold period: 1–3 trading days
2. Never hold through earnings announcements
3. Account for daily rebalancing decay (path dependency)
4. Do not buy after a 15%+ single-day run
5. Size position for max 1% portfolio loss if fully wrong
6. Exit plan always defined at entry

---

## Deployment

### Vercel (Frontend)
- Auto-deploy from `main`
- Env vars: `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `AUTH_SECRET`, `NEXT_PUBLIC_BACKEND_URL`

### Railway (Backend)
- Python 3.12 service: `uvicorn main:app --host 0.0.0.0 --port 8001`
- PostgreSQL plugin attached
- Cron: `POST /jobs/nightly` at 11 PM ET (`0 4 * * * UTC`)
- Env vars: `GOOGLE_CLIENT_ID`, `ANTHROPIC_API_KEY`, `FINNHUB_API_KEY`, `DATABASE_URL`, `FRONTEND_URL`, `JOB_SECRET`, `ADMIN_SECRET`

### DB Migrations
`_migrate_db()` in `main.py` runs at startup — adds missing columns via `ALTER TABLE` using the inspector pattern. No migration framework needed for SQLite/PostgreSQL compatibility. All new columns are nullable.

**Never use `DATETIME` in raw SQL migrations — PostgreSQL rejects it. Always use `TIMESTAMP`.**
