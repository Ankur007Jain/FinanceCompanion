# FinanceCompanion

AI-powered stock advisor for busy working professionals. Acts like a trusted friend who happens to be a finance expert — confident, specific, grounded in real data, zero hallucinations.

> **Not a finance expert? Start here:** [How It Works — Plain English Guide](Docs/HOW_IT_WORKS.md)

---

## What It Does

- **Nightly AI Analysis** — six parallel agents analyze every stock in your watchlist after market close: Price, News, Events, Analyst, Ripple Effects, and Verdict
- **Clear Verdicts** — BUY / HOLD / SELL / WATCH with specific entry target, exit target, stop loss, conviction score, and position size recommendation
- **Past Analyses History** — see the last 30 days of verdicts per stock with day change %, RSI, conviction score, and one-line reasoning — all without leaving the dashboard
- **AI Report** — on-demand Sonnet synthesis of the last 30 analyses: verdict trajectory, conviction trend, price target accuracy, what the AI got right/wrong, what to watch next
- **Self-Improving AI** — performance retrospective injected into every nightly run so the Verdict Agent sees what actually happened after its last calls; report learnings written back to StockMemory
- **Two Simulation Modes** — Autopilot (AI acts on virtual $10K autonomously) + Co-pilot (AI recommends, you approve/skip/override)
- **Financial Chatbot** — full stock context pre-loaded; ask follow-up questions without re-explaining anything; web search enabled for real-time data
- **Smart Skip** — quiet stocks (price <2% move, no events, same verdict 3 days) skip LLM and reuse yesterday's analysis, cutting cost ~65% on large watchlists
- **Token Cost Tracking** — every analysis records input/output/cache tokens and USD cost

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 15 + NextAuth v5 + Tailwind CSS + TypeScript |
| Backend | FastAPI + SQLAlchemy + Python 3.12 |
| Database | SQLite (local) → PostgreSQL (Railway) |
| AI — reasoning | Claude Sonnet 4.6 (verdict, chatbot, report) |
| AI — background | Claude Haiku 4.5 (news summary, ripple, memory, title gen) |
| Market Data | yfinance (primary) + Finnhub (secondary, cross-validation) |
| Technical Indicators | pandas-ta (computed from yfinance price data) |
| Auth | Google OAuth via NextAuth v5 |
| Deploy | Vercel (frontend) + Railway (backend) |

---

## Quick Start

### Prerequisites
- Node.js 20+ and Python 3.12+
- Google OAuth credentials ([console.cloud.google.com](https://console.cloud.google.com))
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Finnhub API key ([finnhub.io](https://finnhub.io) — free tier)

### Setup

```bash
# 1. Clone and install
git clone https://github.com/Ankur007Jain/FinanceCompanion.git
cd FinanceCompanion
npm install
cd backend && pip install -r requirements.txt && cd ..

# 2. Configure environment
cp .env.local.example .env.local          # fill in Google OAuth + backend URL
cp backend/.env.example backend/.env      # fill in API keys

# 3. Run
# Terminal 1 — backend
cd backend && uvicorn main:app --host 0.0.0.0 --port 8001

# Terminal 2 — frontend
npm run dev -- --port 3000
```

Open [http://localhost:3000](http://localhost:3000) and sign in with Google.

### Test the Nightly Pipeline

```bash
# Run analysis for NFLX only
curl -X POST http://localhost:8001/jobs/nightly \
  -H "Content-Type: application/json" \
  -d '{"secret": "your-job-secret", "tickers": ["NFLX"]}'

# Run for all watchlisted tickers
curl -X POST http://localhost:8001/jobs/nightly \
  -H "Content-Type: application/json" \
  -d '{"secret": "your-job-secret"}'
```

---

## Architecture

```
Browser → Next.js (Vercel) → FastAPI (Railway) → PostgreSQL
                                    ↓
                     Nightly Agent Pipeline (11 PM ET)
                     ├── Price Agent    (yfinance + Finnhub, cross-validated)
                     ├── News Agent     (yfinance + Finnhub → Haiku summary)
                     ├── Event Agent    (earnings dates + Fed calendar)
                     ├── Analyst Agent  (consensus, cross-validated)
                     ├── Ripple Agent   (Haiku — 2nd/3rd order effects)
                     └── Verdict Agent  (Sonnet — synthesizes all signals)
                              ↓
                     Performance Retrospective (factual — what happened after past verdicts)
                              ↓
                     StockMemory update (Haiku — nightly + after report generation)
```

All 4 data agents run in parallel per ticker. All tickers run in parallel. Results are saved as `StockAnalysis` (global per ticker, not per user). Last 5 analyses + performance retrospective are fed into the Verdict Agent each night.

---

## Key Design Decisions

- **WATCH is a valid verdict** — wrong advice is worse than no advice
- **Two-source cross-validation** — yfinance vs Finnhub; conflicts surfaced, never hidden
- **Global analysis** — one `StockAnalysis` per ticker per day, shared across all users watching the same stock
- **Signal convergence floor** — 5+ of 7 independent signals must confirm before BUY is eligible
- **Performance retrospective** — Verdict Agent sees what actually happened after its last calls before issuing today's verdict
- **Memory from reports** — user-generated reports feed lessons back into StockMemory
- **Important day flagging** — verdict reversals, earnings proximity, major catalysts
- **Leveraged ETF rules** — max hold 1–3 days, never through earnings, enforced automatically
- **Smart skip** — quiet stocks reuse yesterday's analysis; UI shows age naturally

---

## Environment Variables

**Backend (`backend/.env`):**
```
GOOGLE_CLIENT_ID=        # From Google Cloud Console
ANTHROPIC_API_KEY=       # From console.anthropic.com
FINNHUB_API_KEY=         # From finnhub.io (free tier works)
DATABASE_URL=sqlite:///./app.db   # Use postgresql://... for Railway
FRONTEND_URL=http://localhost:3000
JOB_SECRET=              # Random string to protect /jobs/nightly
ADMIN_SECRET=            # Random string for admin endpoints
```

**Frontend (`.env.local`):**
```
AUTH_GOOGLE_ID=          # From Google Cloud Console
AUTH_GOOGLE_SECRET=      # From Google Cloud Console
AUTH_SECRET=             # Random 32+ char string (openssl rand -hex 32)
NEXT_PUBLIC_BACKEND_URL=http://localhost:8001
```

---

## Running Tests

```bash
# Backend unit tests
cd backend && pytest tests/ -v

# Frontend unit tests
npm test

# E2E smoke tests (requires both servers running)
npm run test:e2e
```

---

## Documentation

| Doc | What It Covers |
|-----|---------------|
| [How It Works](Docs/HOW_IT_WORKS.md) | Plain-English explanation of every feature — start here if you're not a finance expert |
| [Inception](Docs/INCEPTION.md) | Product vision, philosophy, and why it was built |
| [Technical](TECHNICAL.md) | Architecture, data model, API endpoints, agent pipeline |
| [Data Sources](Docs/DATA_SOURCES.md) | yfinance and Finnhub field reference |
| [Verdict Trust Strategy](Docs/verdict-trust-strategy.md) | How the Verdict Agent earns trust through the conviction/scenario framework |

---

## Deployment

See [TECHNICAL.md](TECHNICAL.md) for full deployment guide to Vercel + Railway.
