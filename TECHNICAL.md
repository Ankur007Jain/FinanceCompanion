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

Nightly (APScheduler or Railway Cron → POST /jobs/nightly):
  For each ticker (all in parallel):
    Price Agent  ─┐
    News Agent   ─┤── asyncio.gather ──► Ripple Agent ──► Verdict Agent
    Event Agent  ─┤
    Analyst Agent─┘
    → persist StockAnalysis → maybe_update_stock_memory()
```

---

## Data Model

### `users`
| Column | Type | Notes |
|--------|------|-------|
| email | VARCHAR PK | Google email |
| tier | VARCHAR | `free` / `pro` |
| is_admin | BOOLEAN | admin flag |
| tokens_used | INTEGER | cumulative across all messages |
| token_limit | INTEGER | NULL = no limit (pro); free = from AppConfig |

### `watchlist_items`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_email | VARCHAR FK | |
| ticker | VARCHAR | e.g. `NFLX` |
| company_name | VARCHAR | e.g. `Netflix Inc.` |
| sector | VARCHAR | e.g. `Technology` |
| is_leveraged | BOOLEAN | true for SOXL, MVLL etc. |
| created_at | DATETIME | |

### `stock_analyses` ← **global per ticker, one per day**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| ticker | VARCHAR | |
| analysis_date | DATE | one row per ticker per day |
| current_price | FLOAT | |
| price_change_pct | FLOAT | |
| week52_high | FLOAT | |
| week52_low | FLOAT | |
| week52_position_pct | FLOAT | |
| ma50 | FLOAT | |
| ma200 | FLOAT | |
| rsi | FLOAT | |
| analyst_consensus | VARCHAR | BUY/HOLD/SELL/STRONG BUY/STRONG SELL |
| analyst_upside_pct | FLOAT | |
| verdict | VARCHAR | BUY/HOLD/SELL/WATCH |
| entry_target | FLOAT | |
| exit_target | FLOAT | |
| reasoning | TEXT | AI reasoning, 10-15 lines |
| news_summary | TEXT | Haiku 3-4 sentence summary |
| events_json | JSON | list of upcoming events |
| ripple_analysis | TEXT | Sonnet 2nd/3rd order effects |
| data_conflicts | TEXT | JSON string of any cross-validation conflicts |
| is_important_day | BOOLEAN | flagged by Verdict Agent |
| importance_reason | TEXT | why it's important |
| created_at | DATETIME | |

### `stock_memories` ← **global per ticker**
| Column | Type | Notes |
|--------|------|-------|
| ticker | VARCHAR PK | |
| memory_narrative | TEXT | prose, max 1200 chars |
| last_updated | DATETIME | |
| update_count | INTEGER | |

### `simulation_portfolios`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_email | VARCHAR FK | |
| mode | VARCHAR | `autopilot` / `copilot` |
| ticker | VARCHAR | |
| virtual_cash | FLOAT | starts at 10000 |
| shares_held | FLOAT | |
| avg_cost | FLOAT | |

### `simulation_trades`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| portfolio_id | INTEGER FK | |
| trade_date | DATE | |
| action | VARCHAR | BUY / SELL |
| shares | FLOAT | |
| price | FLOAT | |
| verdict_at_time | VARCHAR | BUY/HOLD/SELL/WATCH |
| realized_pnl | FLOAT | NULL until sell |

### `copilot_decisions`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_email | VARCHAR FK | |
| analysis_id | INTEGER FK | |
| decision | VARCHAR | `approve` / `skip` / `override` |
| override_action | VARCHAR | BUY/SELL/HOLD if decision=override |
| decided_at | DATETIME | |

### `conversations`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_email | VARCHAR FK | |
| ticker | VARCHAR | optional — scopes context |
| title | VARCHAR | Haiku-generated |
| created_at | DATETIME | |

### `messages`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| conversation_id | INTEGER FK | |
| role | VARCHAR | `user` / `assistant` |
| content | TEXT | |
| model_used | VARCHAR | |
| input_tokens | INTEGER | |
| output_tokens | INTEGER | |
| cache_read_tokens | INTEGER | |
| cache_write_tokens | INTEGER | |
| created_at | DATETIME | |

### `app_config`
| Column | Type | Notes |
|--------|------|-------|
| key | VARCHAR PK | e.g. `free_tier_token_limit` |
| value | VARCHAR | |

---

## API Endpoints

### Auth
| Method | Path | Notes |
|--------|------|-------|
| POST | `/auth/verify` | Verify Google id_token, upsert user, return user info |

### Watchlist
| Method | Path | Notes |
|--------|------|-------|
| GET | `/watchlist?id_token=` | All watchlist items for user |
| POST | `/watchlist?id_token=` | Add ticker (body: ticker, company_name, sector, is_leveraged) |
| DELETE | `/watchlist/{ticker}?id_token=` | Remove ticker |

### Analysis
| Method | Path | Notes |
|--------|------|-------|
| GET | `/analysis/digest?id_token=` | Today's analysis for all user's watchlist tickers |
| GET | `/analysis/{ticker}/latest` | Most recent analysis for any ticker |
| GET | `/analysis/{ticker}/history?days=30` | Last N days of analysis per ticker |

### Chat / Streaming
| Method | Path | Notes |
|--------|------|-------|
| GET | `/conversations?id_token=` | List user's conversations |
| POST | `/conversations?id_token=` | Create conversation (body: ticker optional, first_message) |
| GET | `/conversations/{id}?id_token=` | Get conversation with messages |
| DELETE | `/conversations/{id}?id_token=` | Delete |
| POST | `/chat/stream` | SSE endpoint (body: conversation_id, message, id_token) |

### Simulation
| Method | Path | Notes |
|--------|------|-------|
| GET | `/simulation/portfolio?id_token=&mode=` | Get portfolio for autopilot or copilot |
| GET | `/simulation/trades?id_token=&mode=` | Trade history |
| POST | `/simulation/copilot-decision` | Record approve/skip/override |

### Jobs (protected by JOB_SECRET)
| Method | Path | Notes |
|--------|------|-------|
| POST | `/jobs/nightly` | Trigger nightly analysis (body: secret, tickers optional) |

### Admin (protected by ADMIN_SECRET)
| Method | Path | Notes |
|--------|------|-------|
| GET | `/admin/users` | All users |
| POST | `/admin/config` | Set AppConfig key/value |

---

## Agent Pipeline

### Execution Order Per Ticker

```
asyncio.gather(
  price_agent.fetch(),
  news_agent.fetch(),
  event_agent.fetch(),
  analyst_agent.fetch(),
)
↓
ripple_agent.analyze(news_summary, price_data, stock_memory)
↓
verdict_agent.generate(all_above + recent_analyses[-5])
↓
persist StockAnalysis
↓
asyncio.create_task(maybe_update_stock_memory())  # fire and forget
```

### Agent → Model Mapping

| Agent | Model | Why |
|-------|-------|-----|
| Price, News, Event, Analyst | No LLM (except news summary → Haiku) | Pure data fetch |
| News summary | claude-haiku-4-5-20251001 | Speed, cost |
| Stock memory update | claude-haiku-4-5-20251001 | Speed, cost |
| Ripple Agent | claude-sonnet-4-6 | Deep reasoning required |
| Verdict Agent | claude-sonnet-4-6 | Synthesizes all signals |
| Chatbot | claude-sonnet-4-6 | Primary user interface |
| Title generation | claude-haiku-4-5-20251001 | Fire-and-forget, low stakes |

---

## Chatbot — SSE + Tool Use Loop

```
POST /chat/stream → generator function
  while True:
    stream = anthropic.messages.stream(...)
    for event in stream:
      if content_block_start + tool_use → collect tool name
      if input_json_delta → accumulate tool input JSON
      if stop_reason == "tool_use":
        yield {"type": "tool_start", "tool": "web_search", "query": ...}
        results = duckduckgo_search(query)
        yield {"type": "tool_result", "query": ..., "count": ...}
        messages.append(assistant_turn)
        messages.append(tool_results_turn)
        continue  # re-enter loop
      if text_delta → yield {"type": "chunk", "text": ...}
      if stop_reason == "end_turn":
        break
  → save message, update token counts
  → asyncio.create_task(generate_title()) if first message
```

---

## Prompt Architecture

`build_system_prompt(user_email, db, conversation_ticker)` returns `(base_prompt, dynamic_context)`:

- **`base_prompt`** (static, cached): FinanceCompanion advisor persona, rules, tone, quality guidelines, leveraged ETF rules
- **`dynamic_context`** (not cached): today's analysis for all user's watchlist stocks, stock memories, open simulation positions, conversation ticker focus if set

Applied in API call:
```python
[
  {"role": "user", "content": [
    {"type": "text", "text": base_prompt, "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": dynamic_context},
    {"type": "text", "text": user_message},
  ]}
]
```

---

## Cross-Validation Logic

For price data (yfinance vs Finnhub):
- Fetch both concurrently via `asyncio.gather`
- If `abs(price_a - price_b) / price_a > 0.02` → flag conflict in `data_conflicts`
- Use yfinance as primary (more reliable for OHLCV)
- Never silently discard the discrepancy

Same pattern for earnings dates and analyst consensus.

---

## Important Day Flagging

Verdict Agent outputs in JSON:
```json
{
  "verdict": "BUY",
  "entry_target": 95.0,
  "exit_target": 110.0,
  "reasoning": "...",
  "conflict_flags": [],
  "is_important_day": true,
  "importance_reason": "Verdict reversal from HOLD to BUY; earnings in 3 days"
}
```

Trigger conditions (any one = important day):
- Verdict reversal from previous day
- Earnings within 5 calendar days
- Major index inclusion/exclusion event
- Analyst rating upgrade/downgrade by major firm
- Significant news catalyst in ripple analysis

---

## Deployment

### Vercel (Frontend)
- Auto-deploy from `main`
- Env vars: `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `AUTH_SECRET`, `NEXT_PUBLIC_BACKEND_URL`

### Railway (Backend)
- Python 3.12 service running `uvicorn main:app --host 0.0.0.0 --port 8001`
- PostgreSQL plugin attached
- Cron: `POST /jobs/nightly` at 11 PM ET nightly (23:00 America/New_York)
- Env vars: `GOOGLE_CLIENT_ID`, `ANTHROPIC_API_KEY`, `FINNHUB_API_KEY`, `DATABASE_URL`, `FRONTEND_URL`, `JOB_SECRET`, `ADMIN_SECRET`

---

## Seed Tickers

| Ticker | Name | Type | Notes |
|--------|------|------|-------|
| SOXQ | PHLX Semiconductor ETF | ETF | Tracks SOX index |
| SOXL | Direxion Semiconductor Bull 3X | Leveraged ETF | 3x SOX, max hold 1-3 days |
| MRVL | Marvell Technology | Stock | Semiconductor, AI-adjacent |
| MVLL | MV Long Long ETF | Leveraged ETF | Confirm classification |
| NFLX | Netflix | Stock | Streamer, tech bellwether |

---

## Leveraged ETF Rules (Enforced by Verdict Agent)

1. Max hold period: 1-3 trading days
2. Never hold through earnings announcements
3. Account for daily rebalancing decay (path dependency)
4. Do not buy after a 15%+ single-day run (chasing)
5. Size position for max 1% portfolio loss if fully wrong
6. Exit plan defined at entry (always set exit_target)

---

## Quality Rules (Zero-Hallucination Policy)

- WATCH is valid — prefer it over a wrong BUY/SELL
- Every data point cited must come from yfinance or Finnhub (no invention)
- Ripple analysis must account for actual physics/economics (not mechanical mappings)
  - Example: SpaceX space data centers ≠ cooling demand (space cooling is easier, not harder)
- Conflict flags surfaced in reasoning, never hidden
- Historical context (last 5 analyses) must be referenced when verdict reverses
