"""Pull all application tables from Railway PostgreSQL into local SQLite.

Parent tables first so FK-referencing rows land after what they point to
(SQLite doesn't enforce FKs by default here, but keeping the order sane
avoids surprises if that ever changes).
"""
import os
import sqlite3
import sys
import psycopg2
import psycopg2.extras

PROD_URL = os.environ["PROD_DB_URL"]
LOCAL_DB = "app.db"

TABLES = [
    "users",
    "watchlist_items",
    "market_data_cache",
    "stock_analyses",
    "stock_memories",
    "stock_reports",
    "ticker_control",
    "app_config",
    "simulation_portfolios",
    "simulation_trades",
    "copilot_decisions",
    "conversations",
    "messages",
    "feedback",
    "ticker_correlations",
]


def sync_table(cur, sq, table: str):
    print(f"Fetching {table}…")
    cur.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()
    print(f"  {len(rows)} rows found")
    if not rows:
        sq.execute(f"DELETE FROM {table}")
        sq.commit()
        return

    cols = [d.name for d in cur.description]
    placeholders = ",".join("?" * len(cols))
    col_list = ",".join(cols)
    sq.execute(f"DELETE FROM {table}")
    sq.executemany(
        f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})",
        [tuple(r[c] for c in cols) for r in rows],
    )
    sq.commit()
    print(f"  ✓ {len(rows)} {table} synced")


def sync(tables=None):
    tables = tables or TABLES
    print("Connecting to Railway PostgreSQL…")
    pg = psycopg2.connect(PROD_URL)
    pg.autocommit = True
    cur = pg.cursor(cursor_factory=psycopg2.extras.DictCursor)

    sq = sqlite3.connect(LOCAL_DB)
    sq.row_factory = sqlite3.Row

    for table in tables:
        try:
            sync_table(cur, sq, table)
        except psycopg2.errors.UndefinedTable:
            pg.rollback()
            print(f"  (skipped {table} — table doesn't exist in prod)")

    cur.close()
    pg.close()
    sq.close()
    print("\nDone. Local SQLite is now populated from production.")


if __name__ == "__main__":
    only = sys.argv[1:] or None
    sync(only)
