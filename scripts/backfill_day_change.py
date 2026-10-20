"""
One-off: recompute stock_analyses.day_change_pct and relative_strength_1d from the raw
yfinance snapshot saved by the same nightly run (market_data_cache.info_json).

Until the quote_fields.py fix, nightly_fetch.py read fast_info.previous_close, which is
unreliable in the pre-market window most runs land in — ~64% of rows since 2026-09-01
had the wrong daily move (and relative strength, which is derived from it).

Only rows whose snapshot is the same quote as the stored price (within 0.5%) are touched;
everything else is reported and left alone. signal_convergence_score is deliberately NOT
recomputed: it's the record of what the system saw when it issued that verdict.

Usage (from repo root):
  DATABASE_URL=... python3 scripts/backfill_day_change.py                 # dry run
  DATABASE_URL=... python3 scripts/backfill_day_change.py --apply --backup old_values.json
"""
import argparse
import json
import math
import os
import sys
from collections import Counter

from sqlalchemy import create_engine, text

from quote_fields import regular_session_quote

_SAME_QUOTE_TOLERANCE = 0.005
# One UPDATE per batch instead of one per row: over Railway's public proxy a round trip is
# ~120ms, so 6,173 single-row updates held one transaction open ~12 minutes and the proxy
# dropped the connection (rolled back cleanly, nothing written). 150 rows x 5 params stays
# under SQLite's bind-parameter limit too.
_BATCH = 150


def _real(v):
    """NaN -> None. One 2026-07-15 run stored NaN (not NULL) for sector change / relative
    strength; NaN never equals itself, so without this those rows look 'unfixed' forever."""
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def corrected_fields(current_price, day_change_pct, sector_day_chg, relative_strength_1d, info):
    """Returns (status, new_day_change_pct, new_relative_strength_1d). status is one of
    'fix', 'ok', 'no_quote', 'different_quote'."""
    day_change_pct, sector_day_chg = _real(day_change_pct), _real(sector_day_chg)
    stored_rel = relative_strength_1d
    relative_strength_1d = _real(relative_strength_1d)
    if not current_price:
        return "no_quote", None, None
    snap_price, prev, _ = regular_session_quote(info)
    if snap_price is None or prev is None:
        return "no_quote", None, None
    if abs(snap_price - current_price) / current_price > _SAME_QUOTE_TOLERANCE:
        return "different_quote", None, None
    new_chg = round((current_price - prev) / prev * 100, 2)
    new_rel = round(new_chg - sector_day_chg, 2) if sector_day_chg is not None else relative_strength_1d
    if new_rel is None:
        rel_ok = stored_rel is None
    else:
        rel_ok = relative_strength_1d is not None and abs(relative_strength_1d - new_rel) < 0.01
    unchanged = day_change_pct is not None and abs(day_change_pct - new_chg) < 0.01 and rel_ok
    return ("ok" if unchanged else "fix"), new_chg, new_rel


def _update_batch(conn, batch):
    params, chg_cases, rel_cases, ids = {}, [], [], []
    for n, f in enumerate(batch):
        params[f"id{n}"] = f["id"]
        params[f"c{n}"] = f["new_day_change_pct"]
        params[f"r{n}"] = f["new_relative_strength_1d"]
        chg_cases.append(f"WHEN :id{n} THEN :c{n}")
        rel_cases.append(f"WHEN :id{n} THEN :r{n}")
        ids.append(f":id{n}")
    conn.execute(text(
        f"UPDATE stock_analyses SET "
        f"day_change_pct = CAST(CASE id {' '.join(chg_cases)} END AS DOUBLE PRECISION), "
        f"relative_strength_1d = CAST(CASE id {' '.join(rel_cases)} END AS DOUBLE PRECISION) "
        f"WHERE id IN ({', '.join(ids)})"
    ), params)


def run(engine, apply=False, backup=None, since="2000-01-01"):
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT a.id, a.ticker, a.analysis_date, a.current_price, a.day_change_pct,
                   a.sector_day_chg, a.relative_strength_1d, m.info_json
            FROM stock_analyses a
            JOIN market_data_cache m ON m.ticker = a.ticker AND m.cache_date = a.analysis_date
            WHERE a.analysis_date >= :since
        """), {"since": since}).fetchall()
        no_snapshot = c.execute(text("""
            SELECT count(*) FROM stock_analyses a
            WHERE a.analysis_date >= :since AND NOT EXISTS (
                SELECT 1 FROM market_data_cache m WHERE m.ticker = a.ticker AND m.cache_date = a.analysis_date)
        """), {"since": since}).scalar()

    counts = Counter()
    fixes = []
    for r in rows:
        try:
            info = json.loads(r.info_json) if r.info_json else {}
        except (TypeError, ValueError):
            info = {}
        status, new_chg, new_rel = corrected_fields(r.current_price, r.day_change_pct, r.sector_day_chg, r.relative_strength_1d, info)
        counts[status] += 1
        if status == "fix":
            fixes.append({
                "id": r.id, "ticker": r.ticker, "analysis_date": str(r.analysis_date),
                "old_day_change_pct": r.day_change_pct, "new_day_change_pct": new_chg,
                "old_relative_strength_1d": r.relative_strength_1d, "new_relative_strength_1d": new_rel,
            })

    summary = {
        "rows_with_snapshot": len(rows), "rows_without_snapshot": no_snapshot,
        "to_fix": counts["fix"], "already_correct": counts["ok"],
        "skipped_no_quote": counts["no_quote"], "skipped_different_quote": counts["different_quote"],
        "sign_flips": sum(1 for f in fixes if f["old_day_change_pct"] and f["old_day_change_pct"] * f["new_day_change_pct"] < 0),
        "were_exactly_zero": sum(1 for f in fixes if f["old_day_change_pct"] == 0.0),
    }

    if apply and fixes:
        if backup:
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
    ap.add_argument("--since", default="2000-01-01", help="only rows with analysis_date >= this")
    args = ap.parse_args()
    if args.apply and not args.backup:
        sys.exit("--apply requires --backup so the old values can be restored")

    summary, fixes = run(create_engine(os.environ["DATABASE_URL"]), args.apply, args.backup, args.since)
    print(json.dumps(summary, indent=2))
    for f in fixes[:10]:
        print(f"  {f['ticker']:6s} {f['analysis_date']}  {f['old_day_change_pct']} -> {f['new_day_change_pct']}  "
              f"(rel {f['old_relative_strength_1d']} -> {f['new_relative_strength_1d']})")
    print("APPLIED" if args.apply else "DRY RUN — nothing written. Re-run with --apply --backup <file>.")


if __name__ == "__main__":
    main()
