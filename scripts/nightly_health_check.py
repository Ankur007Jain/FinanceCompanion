"""
Nightly pipeline — final check: fail the run when a whole data source is missing from the
analyses just saved, so GitHub reports a failed workflow.

Deliberately not an AI judgement. News went dark for three weeks from 2026-10-02, and Gemini
verdicts for three weeks from 2026-11-06 — the second while the AI sentinel was reporting
"all clear, pre-existing known gap".

Usage: python3 scripts/nightly_health_check.py [--since YYYY-MM-DD]
Requires BACKEND_URL and ADMIN_SECRET in the environment. Stdlib only.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# Normal is ~0% for Gemini and 5-9% for news (mutual funds and tiny ETFs rarely have any).
MAX_MISSING_PCT = 20
# column in /jobs/admin/data-quality -> what to call it in the alert
CHECKS = {"verdict_b": "Gemini second opinion", "news": "News headlines"}


def evaluate(stats: dict, since: str, max_pct: float = MAX_MISSING_PCT) -> list[str]:
    """Problems found in analyses dated `since` or later (a run can cross midnight)."""
    days = [v for d, v in stats.get("null_rates_by_date", {}).items() if d >= since]
    if not sum(v["rows"] for v in days):
        return [f"No analyses saved since {since}."]
    problems = []
    for column, label in CHECKS.items():
        reported = [v for v in days if column in v["null_pct"]]
        rows = sum(v["rows"] for v in reported)
        if not rows:
            problems.append(f"{label}: not reported by the backend since {since}.")
            continue
        missing = sum(v["rows"] * v["null_pct"][column] for v in reported) / rows
        if missing > max_pct:
            problems.append(f"{label} missing for {missing:.0f}% of {rows} analyses since {since} (limit {max_pct}%).")
    return problems


def fetch_stats(backend: str, secret: str, attempts: int = 3) -> dict:
    url = f"{backend}/jobs/admin/data-quality?x_admin_secret={urllib.parse.quote(secret)}&days=3"
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if attempt == attempts - 1:
                raise RuntimeError(f"data-quality endpoint unreachable: {type(e).__name__}") from None
            time.sleep(10 * (attempt + 1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=datetime.now(timezone.utc).date().isoformat())
    args = ap.parse_args(argv)
    problems = evaluate(fetch_stats(os.environ["BACKEND_URL"], os.environ["ADMIN_SECRET"]), args.since)
    for p in problems:
        print(f"::error title=Nightly data check::{p}")
    if problems:
        return 1
    print(f"Data check passed: Gemini and news present for analyses since {args.since}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
