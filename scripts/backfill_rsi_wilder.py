"""
One-off: rewrite recent stock_analyses.rsi values from the old simple-average RSI to standard
Wilder RSI (scripts/indicators.py), so the 2026-10-23 switch doesn't show every ticker's RSI
jumping in the "what changed" digest or in the history the agent and chat read.

A row is rewritten only when its stored value is reproduced exactly by the old formula from
price_history — that pins which bar the nightly used (normally the last close before the run
date; a retry run during market hours may have included that day's bar). Rows that can't be
reproduced are reported and left alone. signal_convergence_score is deliberately NOT
recomputed: it's the record of what the system saw when it issued that verdict.

Usage (from repo root):
  DATABASE_URL=... python3 scripts/backfill_rsi_wilder.py                      # dry run, last 30 days
  DATABASE_URL=... python3 scripts/backfill_rsi_wilder.py --apply --backup old_rsi.json
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import Float, case, cast, column, create_engine, table, text, update

from indicators import wilder_rsi

_BATCH = 150
_stock_analyses = table("stock_analyses", column("id"), column("rsi"))


def cutler_rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """The formula nightly_fetch.py used before 2026-10-23, kept only to verify rows."""
    d = close.diff()
    gain = d.clip(lower=0).rolling(length).mean()
    loss = (-d.clip(upper=0)).rolling(length).mean()
    return (100 - 100 / (1 + gain / loss)).where(loss != 0, 50.0)


def corrected_rsi(stored: float, analysis_date: date, old: pd.Series, new: pd.Series):
    """Returns (status, new_rsi). status: 'fix', 'ok', 'no_match' or 'no_prices'.
    old/new are the two RSI series for the ticker, indexed by bar date."""
    prior = [d for d in old.index if d < analysis_date]
    candidates = ([prior[-1]] if prior else []) + ([analysis_date] if analysis_date in old.index else [])
    if not candidates:
        return "no_prices", None
    for bar in candidates:
        if pd.notna(old[bar]) and abs(round(float(old[bar]), 1) - stored) < 0.05:
            value = round(float(new[bar]), 1)
            return ("ok" if abs(value - stored) < 0.05 else "fix"), value
    return "no_match", None


def _update_batch(conn, batch):
    conn.execute(
        update(_stock_analyses)
        .where(_stock_analyses.c.id.in_([f["id"] for f in batch]))
        .values(rsi=cast(case({f["id"]: f["new_rsi"] for f in batch}, value=_stock_analyses.c.id), Float))
    )


def run(engine, apply=False, backup=None, since=None):
    since = since or (date.today() - timedelta(days=30)).isoformat()
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT id, ticker, analysis_date, rsi FROM stock_analyses "
            "WHERE analysis_date >= :since AND rsi IS NOT NULL ORDER BY ticker, analysis_date"
        ), {"since": since}).fetchall()
        series = {}
        for ticker in sorted({r.ticker for r in rows}):
            bars = c.execute(text("SELECT date, close FROM price_history WHERE symbol = :s ORDER BY date"), {"s": ticker}).fetchall()
            close = pd.Series([b.close for b in bars], index=[pd.Timestamp(b.date).date() for b in bars], dtype=float)
            series[ticker] = (cutler_rsi(close), wilder_rsi(close))

    counts, fixes = Counter(), []
    for r in rows:
        d = r.analysis_date if isinstance(r.analysis_date, date) else date.fromisoformat(str(r.analysis_date))
        status, value = corrected_rsi(float(r.rsi), d, *series[r.ticker])
        counts[status] += 1
        if status == "fix":
            fixes.append({"id": r.id, "ticker": r.ticker, "analysis_date": d.isoformat(), "old_rsi": float(r.rsi), "new_rsi": value})

    summary = {
        "since": since, "rows": len(rows), "to_fix": counts["fix"], "already_standard": counts["ok"],
        "skipped_no_match": counts["no_match"], "skipped_no_prices": counts["no_prices"],
    }
    if apply and fixes:
        with open(backup, "w") as f:
            json.dump(fixes, f, indent=1)
        with engine.begin() as c:
            for i in range(0, len(fixes), _BATCH):
                _update_batch(c, fixes[i:i + _BATCH])
    return summary, fixes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--backup", help="write old values to this JSON file before applying")
    ap.add_argument("--since", help="only rows with analysis_date >= this (default: 30 days ago)")
    args = ap.parse_args()
    if args.apply and not args.backup:
        sys.exit("--apply requires --backup so the old values can be restored")

    summary, fixes = run(create_engine(os.environ["DATABASE_URL"]), args.apply, args.backup, args.since)
    print(json.dumps(summary, indent=2))
    for f in sorted(fixes, key=lambda f: -abs(f["new_rsi"] - f["old_rsi"]))[:10]:
        print(f"  {f['ticker']:6s} {f['analysis_date']}  {f['old_rsi']} -> {f['new_rsi']}")
    print("APPLIED" if args.apply else "DRY RUN — nothing written. Re-run with --apply --backup <file>.")


if __name__ == "__main__":
    main()
