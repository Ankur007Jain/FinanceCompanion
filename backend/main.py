from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, inspect

from database import Base, engine, SessionLocal
from models import AppConfig  # noqa: F401 — ensures table is registered
from routers import auth, watchlist, analysis, simulation, conversations, streaming, jobs

app = FastAPI(title="FinanceCompanion API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
    allow_credentials=True,
)

app.include_router(auth.router)
app.include_router(watchlist.router)
app.include_router(analysis.router)
app.include_router(simulation.router)
app.include_router(conversations.router)
app.include_router(streaming.router)
app.include_router(jobs.router)


def _migrate_db():
    with engine.connect() as conn:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if "conversations" in tables:
            cols = {c["name"] for c in inspector.get_columns("conversations")}
            if "ticker" not in cols:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN ticker VARCHAR"))
            if "updated_at" not in cols:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN updated_at DATETIME"))
            conn.commit()

        if "stock_analyses" in tables:
            cols = {c["name"] for c in inspector.get_columns("stock_analyses")}
            new_cols = {
                "pe_trailing":           "FLOAT",
                "pe_forward":            "FLOAT",
                "revenue_growth":        "FLOAT",
                "earnings_growth":       "FLOAT",
                "profit_margin":         "FLOAT",
                "debt_to_equity":        "FLOAT",
                "free_cashflow":         "FLOAT",
                "return_on_equity":      "FLOAT",
                "beta":                  "FLOAT",
                "short_float_pct":       "FLOAT",
                "short_ratio":           "FLOAT",
                "inst_ownership_pct":    "FLOAT",
                "insider_ownership_pct": "FLOAT",
                "sp500_52w_change":      "FLOAT",
                "stock_52w_change":      "FLOAT",
                "dividend_yield":        "FLOAT",
                "market_cap":            "FLOAT",
                "sector":                "VARCHAR",
                "industry":              "VARCHAR",
                "fundamentals_json":     "TEXT",
                "stop_loss":             "FLOAT",
                "hold_period":           "VARCHAR",
                "conviction_score":      "INTEGER",
                "risk_level":            "VARCHAR",
                "confidence":            "VARCHAR",
                "bull_case":             "TEXT",
                "bear_case":             "TEXT",
                "thesis_invalidation":   "TEXT",
            }
            for col, typ in new_cols.items():
                if col not in cols:
                    # col/typ come from a hardcoded dict — not user input; DDL cannot use bind params
                    conn.execute(text(f"ALTER TABLE stock_analyses ADD COLUMN {col} {typ}"))  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
            conn.commit()

        if "market_data_cache" not in tables:
            conn.execute(text("""
                CREATE TABLE market_data_cache (
                    ticker VARCHAR NOT NULL,
                    cache_date DATE NOT NULL,
                    info_json TEXT,
                    history_json TEXT,
                    news_json TEXT,
                    calendar_json TEXT,
                    created_at DATETIME,
                    PRIMARY KEY (ticker, cache_date)
                )
            """))
            conn.commit()

        is_pg = str(engine.url).startswith("postgresql")
        insert_ignore = (
            "INSERT INTO app_config (key, value) VALUES (:k, :v) ON CONFLICT (key) DO NOTHING"
            if is_pg
            else "INSERT OR IGNORE INTO app_config (key, value) VALUES (:k, :v)"
        )
        conn.execute(text(insert_ignore), {"k": "free_tier_token_limit", "v": "100000"})
        conn.commit()


Base.metadata.create_all(bind=engine)
_migrate_db()


@app.get("/health")
def health():
    db_url = os.getenv("DATABASE_URL", "")
    db_type = "postgresql" if db_url.startswith("postgresql") else "sqlite"
    return {
        "status": "ok",
        "service": "FinanceCompanion API",
        "version": app.version,
        "db": db_type,
        "ai_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
    }
