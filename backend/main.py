from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, inspect

from database import Base, engine, SessionLocal
from models import AppConfig, StockReport  # noqa: F401 — ensures tables are registered
from routers import auth, watchlist, analysis, simulation, conversations, streaming, jobs, translate

app = FastAPI(title="FinanceCompanion API", version="0.1.0")

_raw_origins = os.getenv("FRONTEND_URL", "http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
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
app.include_router(translate.router)


def _migrate_db():
    with engine.connect() as conn:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if "watchlist_items" in tables:
            wl_cols = {c["name"] for c in inspector.get_columns("watchlist_items")}
            if "last_read_analysis_id" not in wl_cols:
                conn.execute(text("ALTER TABLE watchlist_items ADD COLUMN last_read_analysis_id VARCHAR"))  # nosemgrep
            if "last_read_at" not in wl_cols:
                conn.execute(text("ALTER TABLE watchlist_items ADD COLUMN last_read_at TIMESTAMP"))  # nosemgrep
            conn.commit()

        if "conversations" in tables:
            cols = {c["name"] for c in inspector.get_columns("conversations")}
            if "ticker" not in cols:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN ticker VARCHAR"))
            if "updated_at" not in cols:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN updated_at TIMESTAMP"))
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
                "entry_quality":         "VARCHAR",
                "hold_and_forget_rating":"VARCHAR",
                "position_size_pct":     "VARCHAR",
                "scenario_bull":         "TEXT",
                "scenario_base":         "TEXT",
                "scenario_bear":         "TEXT",
                "scenario_bull_pct":     "FLOAT",
                "scenario_base_pct":     "FLOAT",
                "scenario_bear_pct":     "FLOAT",
                "scenario_bull_prob":    "INTEGER",
                "scenario_base_prob":    "INTEGER",
                "scenario_bear_prob":    "INTEGER",
                "dont_panic_note":           "TEXT",
                "signal_convergence_score":  "INTEGER",
                "convergence_details":       "TEXT",
            }
            for col, typ in new_cols.items():
                if col not in cols:
                    # col/typ come from a hardcoded dict — not user input; DDL cannot use bind params
                    conn.execute(text(f"ALTER TABLE stock_analyses ADD COLUMN {col} {typ}"))  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
            conn.commit()

        if "users" in tables:
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            if "portfolio_size" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN portfolio_size FLOAT"))  # nosemgrep
            conn.commit()

        if "stock_analyses" in tables:
            sa_cols = {c["name"] for c in inspector.get_columns("stock_analyses")}
            for col, typ in [
                ("verdict_a", "VARCHAR"),
                ("verdict_b", "VARCHAR"),
                ("verdict_agreement", "BOOLEAN"),
                ("split_reason", "TEXT"),
                ("support_20d", "FLOAT"),
                ("resistance_20d", "FLOAT"),
                ("pivot_point", "FLOAT"),
                ("pivot_r1", "FLOAT"),
                ("pivot_s1", "FLOAT"),
                ("sp500_day_chg", "FLOAT"),
                ("sector_etf", "VARCHAR"),
                ("sector_day_chg", "FLOAT"),
                ("relative_strength_1d", "FLOAT"),
                ("fh_price", "FLOAT"),
                ("fh_analyst_consensus", "VARCHAR"),
                ("data_conflicts", "TEXT"),
            ]:
                if col not in sa_cols:
                    conn.execute(text(f"ALTER TABLE stock_analyses ADD COLUMN {col} {typ}"))  # nosemgrep
            conn.commit()

        if "stock_analyses" in tables:
            sa_cols2 = {c["name"] for c in inspector.get_columns("stock_analyses")}
            for col, typ in [
                ("tokens_input",       "INTEGER"),
                ("tokens_output",      "INTEGER"),
                ("tokens_cache_read",  "INTEGER"),
                ("tokens_cache_write", "INTEGER"),
                ("cost_usd",           "FLOAT"),
            ]:
                if col not in sa_cols2:
                    conn.execute(text(f"ALTER TABLE stock_analyses ADD COLUMN {col} {typ}"))  # nosemgrep
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
                    created_at TIMESTAMP,
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
