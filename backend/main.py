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
    return {"status": "ok", "service": "FinanceCompanion API"}
