"""Pull stock_analyses and stock_memories from Railway PostgreSQL into local SQLite."""
import os
import sqlite3
import psycopg2
import psycopg2.extras

PROD_URL = os.environ["PROD_DB_URL"]
LOCAL_DB  = "app.db"

def sync():
    print("Connecting to Railway PostgreSQL…")
    pg = psycopg2.connect(PROD_URL)
    pg.autocommit = True
    cur = pg.cursor(cursor_factory=psycopg2.extras.DictCursor)

    sq = sqlite3.connect(LOCAL_DB)
    sq.row_factory = sqlite3.Row

    # ── stock_analyses ────────────────────────────────────────────────────────
    print("Fetching stock_analyses…")
    cur.execute("SELECT * FROM stock_analyses ORDER BY analysis_date DESC")
    rows = cur.fetchall()
    print(f"  {len(rows)} rows found")

    if rows:
        cols = [d.name for d in cur.description]
        placeholders = ",".join("?" * len(cols))
        col_list = ",".join(cols)
        sq.execute("DELETE FROM stock_analyses")
        sq.executemany(
            f"INSERT OR REPLACE INTO stock_analyses ({col_list}) VALUES ({placeholders})",
            [tuple(r[c] for c in cols) for r in rows],
        )
        sq.commit()
        print(f"  ✓ {len(rows)} stock_analyses synced")

    # ── stock_memories ────────────────────────────────────────────────────────
    print("Fetching stock_memories…")
    cur.execute("SELECT * FROM stock_memories")
    rows = cur.fetchall()
    print(f"  {len(rows)} rows found")

    if rows:
        cols = [d.name for d in cur.description]
        placeholders = ",".join("?" * len(cols))
        col_list = ",".join(cols)
        sq.execute("DELETE FROM stock_memories")
        sq.executemany(
            f"INSERT OR REPLACE INTO stock_memories ({col_list}) VALUES ({placeholders})",
            [tuple(r[c] for c in cols) for r in rows],
        )
        sq.commit()
        print(f"  ✓ {len(rows)} stock_memories synced")

    cur.close()
    pg.close()
    sq.close()
    print("\nDone. Local SQLite is now populated from production.")

if __name__ == "__main__":
    sync()
