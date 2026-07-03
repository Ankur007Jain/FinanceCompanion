# CLAUDE.md — FinanceCompanion

## Who You Are Working With

You are working with Ankur — a Data Engineering Manager who builds full-stack AI apps via vibe coding.
He knows SQL, Python, ETL, and data systems deeply. He is NOT a frontend expert.
Keep responses short and direct. Never auto-push to git.

---

## Stack (Non-Negotiable)

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js (App Router), NextAuth v5, Tailwind CSS, TypeScript |
| Backend | FastAPI + Uvicorn, SQLAlchemy, Pydantic |
| Database | SQLite locally, PostgreSQL on Railway |
| AI — chat | `claude-sonnet-4-6` (chatbot, verdict agent, ripple agent) |
| AI — background | `claude-haiku-4-5-20251001` (news summary, stock memory update, title gen) |
| Market Data | yfinance (primary) + Finnhub (secondary, cross-validation) |
| Technical Indicators | pandas-ta (computed from yfinance price data) |
| Web Search (chatbot) | duckduckgo-search (no API key needed) |
| Auth | Google OAuth via NextAuth v5 |
| Deploy | Vercel (frontend) + Railway (backend) |

---

## Architecture

```
Browser → Next.js (Vercel) → FastAPI (Railway) → PostgreSQL
                                    ↓
                     Nightly Agent Pipeline (APScheduler)
                     ├── Price Agent    (yfinance + Finnhub)
                     ├── News Agent     (yfinance + Finnhub → Haiku summary)
                     ├── Event Agent    (earnings dates + Fed calendar)
                     ├── Analyst Agent  (yfinance + Finnhub, cross-validated)
                     ├── Ripple Agent   (Sonnet — 2nd/3rd order effects)
                     └── Verdict Agent  (Sonnet — synthesizes all, checks contradictions)
```

---

## Key Design Rules

- **StockAnalysis is global per ticker** — one analysis per ticker per day, shared across all users
- **StockMemory is global per ticker** — prose narrative updated by Haiku after each nightly run
- **All 4 data agents run in parallel per ticker**; all tickers run in parallel across nightly run
- **Historical context** — Verdict Agent always receives last 5 analyses per ticker
- **Important day flagging** — Verdict Agent sets `is_important_day=true` for verdict reversals,
  major catalysts, earnings proximity (<5 days), or index events
- **Quality over quantity** — if signals are weak or contradictory, issue WATCH not a wrong verdict
- **Two-source cross-validation** — yfinance vs Finnhub; conflicts flagged, never silently resolved
- **Leveraged ETF rules** — applied automatically by Verdict Agent (max hold 1-3 days, no earnings hold)

---

## Running Locally

```bash
# Backend
cd backend
cp .env.example .env   # fill in your keys
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001

# Frontend
cp .env.local.example .env.local   # fill in your keys
npm install
npm run dev -- --port 3000

# Trigger nightly analysis manually (test with NFLX)
curl -X POST http://localhost:8001/jobs/nightly \
  -H "Content-Type: application/json" \
  -d '{"secret": "your-job-secret", "tickers": ["NFLX"]}'
```

---

## Local Dev Auth Bypass — ALWAYS USE THIS

`backend/.env` has `TEST_MODE=true`. This enables a token bypass so you **never need a real Google token** when testing locally.

**Token format:** `test-token-{email}`

```bash
# Authenticate as any user — no Google needed
TOK="test-token-ankur@test.com"

# Verify it works
curl http://localhost:8001/auth/verify \
  -H "Content-Type: application/json" \
  -d "{\"id_token\": \"$TOK\"}"

# Use in any endpoint
curl "http://localhost:8001/analysis/digest?id_token=$TOK"
curl "http://localhost:8001/watchlist?id_token=$TOK"
curl -X POST "http://localhost:8001/watchlist?id_token=$TOK" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"AAPL","company_name":"Apple Inc."}'
curl -X PATCH "http://localhost:8001/watchlist/AAPL/portfolio?id_token=$TOK" \
  -H "Content-Type: application/json" \
  -d '{"shares":13.29,"avg_cost":185.50}'
curl -X POST "http://localhost:8001/portfolio/import/preview?id_token=$TOK" \
  -F "file=@holdings.csv"
```

> **Never commit `TEST_MODE=true` to production.** Railway env vars do not have this — it's `.env` local only.

---

## Environment Variables

**Backend (`backend/.env`):**
```
GOOGLE_CLIENT_ID=
ANTHROPIC_API_KEY=
FINNHUB_API_KEY=
DATABASE_URL=sqlite:///./app.db
FRONTEND_URL=http://localhost:3000
JOB_SECRET=
ADMIN_SECRET=
```

**Frontend (`.env.local`):**
```
AUTH_GOOGLE_ID=
AUTH_GOOGLE_SECRET=
AUTH_SECRET=
NEXT_PUBLIC_BACKEND_URL=http://localhost:8001
```

---

## Data Models (Key Tables)

| Table | Key Fields | Notes |
|-------|-----------|-------|
| `users` | email PK, tier, tokens_used | Standard auth |
| `watchlist_items` | user_email, ticker | Per-user; analysis is global |
| `stock_analyses` | ticker, analysis_date, verdict, is_important_day | One per ticker per day |
| `stock_memories` | ticker PK, memory_narrative | Updated when significant |
| `simulation_portfolios` | user_email, mode (autopilot/copilot), ticker | Virtual $10k per mode |
| `copilot_decisions` | user_email, analysis_id, decision (approve/skip/override) | Co-pilot audit trail |
| `conversations` | user_email, ticker (optional) | Chatbot sessions |

---

## Git Workflow

1. Never commit directly to `main` — always use a feature branch
2. Never `git push` without explicit instruction
3. When asked to "push and merge" → `gh pr create`, return the URL

---

## Testing

```bash
# Backend
cd backend && pytest tests/ -v

# Frontend
npm test

# E2E
npm run test:e2e
```
