# FinanceCompanion

AI-powered stock advisor for busy working professionals. Acts like a trusted friend who happens to be a finance expert — confident, specific, grounded in real data, zero hallucinations.

## What It Does

- **Daily Digest** — every morning, AI analyzes your watchlist stocks: verdict (BUY/HOLD/SELL/WATCH), entry/exit targets, 52-week position, RSI, analyst consensus, upcoming events
- **Two Simulation Modes** — Autopilot (AI acts on virtual $10K autonomously) + Co-pilot (AI recommends, you approve/skip/override)
- **Financial Chatbot** — full stock context pre-loaded; ask follow-up questions without re-explaining anything; web search enabled for real-time data
- **Multi-agent Nightly Pipeline** — 6 parallel AI agents per ticker: Price, News, Events, Analyst, Ripple (2nd-order effects), Verdict

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 15 + NextAuth v5 + Tailwind CSS + TypeScript |
| Backend | FastAPI + SQLAlchemy + Python 3.12 |
| Database | SQLite (local) → PostgreSQL (Railway) |
| AI | Claude Sonnet 4.6 (chat/verdict/ripple) + Claude Haiku 4.5 (summaries/titles) |
| Market Data | yfinance (primary) + Finnhub (secondary, cross-validation) |
| Auth | Google OAuth via NextAuth v5 |
| Deploy | Vercel (frontend) + Railway (backend) |

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

## Architecture

```
Browser → Next.js (Vercel) → FastAPI (Railway) → PostgreSQL
                                    ↓
                     Nightly Agent Pipeline (11 PM ET)
                     ├── Price Agent    (yfinance + Finnhub, cross-validated)
                     ├── News Agent     (yfinance + Finnhub → Haiku summary)
                     ├── Event Agent    (earnings dates + Fed calendar)
                     ├── Analyst Agent  (consensus from both sources)
                     ├── Ripple Agent   (Sonnet — 2nd/3rd order effects)
                     └── Verdict Agent  (Sonnet — synthesizes all signals)
```

All 4 data agents run in parallel per ticker. All tickers run in parallel. Results are saved as `StockAnalysis` (global per ticker, not per user). Last 5 analyses are fed back into the Verdict Agent each night for historical context.

## Seed Tickers

| Ticker | Name | Type |
|--------|------|------|
| SOXQ | PHLX Semiconductor ETF | ETF |
| SOXL | Direxion Semiconductor Bull 3X | Leveraged ETF |
| MRVL | Marvell Technology | Stock |
| NFLX | Netflix | Stock |

## Key Design Decisions

- **Quality over quantity** — WATCH is a valid verdict. Wrong advice is worse than no advice.
- **Two-source cross-validation** — yfinance vs Finnhub; conflicts surfaced, never hidden.
- **Global analysis** — same StockAnalysis for all users watching the same ticker.
- **Important day flagging** — Verdict Agent marks days with verdict reversals, earnings proximity, or major catalysts.
- **Leveraged ETF rules** — automatically enforced: max hold 1-3 days, never hold through earnings.

## Environment Variables

**Backend (`backend/.env`):**
```
GOOGLE_CLIENT_ID=        # From Google Cloud Console
ANTHROPIC_API_KEY=       # From console.anthropic.com
FINNHUB_API_KEY=         # From finnhub.io (free tier works)
DATABASE_URL=sqlite:///./app.db   # Use postgres://... for Railway
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

## Running Tests

```bash
# Backend unit tests
cd backend && pytest tests/ -v

# Frontend unit tests
npm test

# E2E smoke tests (requires both servers running)
npm run test:e2e
```

## Deployment

See [TECHNICAL.md](TECHNICAL.md) for full deployment guide to Vercel + Railway.
