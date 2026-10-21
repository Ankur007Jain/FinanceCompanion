"""
Nightly pipeline — Step 4: build and POST one ticker's analysis to the backend.
Usage: python3 scripts/nightly_ingest_analysis.py TICKER [--dry-run]
Requires BACKEND_URL and JOB_SECRET in the environment (not needed with --dry-run).

Reads the files earlier steps already wrote:
  /tmp/summary_TICKER.json       (Step 1, nightly_fetch.py)
  /tmp/convergence_TICKER.json   (Step 2, compute_signal_convergence.py)
  /tmp/verdict_a_TICKER.json     (Step 3a, written by the agent)
  /tmp/verdict_b_TICKER.json     (Step 3b, nightly_verdict_b.py — optional)
  /tmp/split_reason_TICKER.txt   (Step 3c, written by the agent — optional)

Why this exists: Step 4 used to ask the agent to hand-build a ~70-field JSON POST from a
mapping list in the prompt. Every batch improvised its own way of doing that (helper
scripts under different names, inline merges, curl -d @file), and the prompt's list itself
omitted fields — `rsi` (issue #132), and `reasoning`, entry/exit targets, news and ripple
text. Batches that followed the list literally saved analyses with no reasoning (5 tickers
on each of 2026-10-12, 10-19 and 10-20). The data shapes never change night to night; only
the improvised code did. This script is that code, written once and tested.
"""
import argparse
import json
import os
import sys
import time
from datetime import date

VERDICTS = {"BUY", "HOLD", "SELL", "WATCH"}

# Step 3c agreement table, as unordered pairs. The prompt's table only listed some orderings
# (e.g. BUY/WATCH but not WATCH/BUY), and agents filled the gaps inconsistently.
_SPLIT_OUTCOME = {
    frozenset({"BUY", "HOLD"}): "WATCH",
    frozenset({"BUY", "SELL"}): "WATCH",
    frozenset({"BUY", "WATCH"}): "WATCH",
    frozenset({"HOLD", "SELL"}): "WATCH",
    frozenset({"HOLD", "WATCH"}): "WATCH",
    frozenset({"SELL", "WATCH"}): "SELL",
}
_CONVICTION_GAP = 30

# payload field -> summary_TICKER.json key
SUMMARY_FIELDS = {
    "current_price": "price", "price_change_pct": "change_pct",
    "week52_high": "hi52", "week52_low": "lo52", "week52_position_pct": "range_pct",
    "ma50": "ma50", "ma200": "ma200", "rsi": "rsi",
    "analyst_consensus": "analyst", "analyst_count": "analyst_count", "analyst_upside_pct": "upside_pct",
    "target_price_mean": "target_mean", "target_price_high": "target_high", "target_price_low": "target_low",
    "support_20d": "support_20d", "resistance_20d": "resistance_20d",
    "pivot_point": "pivot", "pivot_r1": "piv_r1", "pivot_s1": "piv_s1",
    "sector": "sector", "industry": "industry",
    "sp500_day_chg": "sp500_day_chg", "sector_etf": "sector_etf", "sector_day_chg": "sector_day_chg",
    "relative_strength_1d": "relative_strength_1d",
    "sp500_52w_change": "sp500_52w_change", "stock_52w_change": "stock_52w_change",
    "sp500_5y_change": "sp500_5y_change", "stock_5y_change": "stock_5y_change",
    "fh_price": "fh_price", "fh_analyst_consensus": "fh_analyst",
    "pe_trailing": "pe_trailing", "pe_forward": "pe_forward",
    "revenue_growth": "revenue_growth", "earnings_growth": "earnings_growth",
    "profit_margin": "profit_margin", "debt_to_equity": "debt_to_equity",
    "free_cashflow": "free_cashflow", "return_on_equity": "return_on_equity", "beta": "beta",
    "short_float_pct": "short_float_pct", "short_ratio": "short_ratio",
    "inst_ownership_pct": "inst_ownership_pct", "insider_ownership_pct": "insider_ownership_pct",
    "dividend_yield": "dividend_yield", "market_cap": "market_cap",
}

# Copied as-is from verdict_a_TICKER.json (the Step 3a schema)
VERDICT_A_FIELDS = [
    "entry_target", "exit_target", "stop_loss", "hold_period", "reasoning", "conviction_score",
    "risk_level", "confidence", "bull_case", "bear_case", "thesis_invalidation", "news_summary",
    "ripple_analysis", "is_important_day", "importance_reason", "entry_quality",
    "hold_and_forget_rating", "position_size_pct",
    "scenario_bull", "scenario_bull_pct", "scenario_bull_prob",
    "scenario_base", "scenario_base_pct", "scenario_base_prob",
    "scenario_bear", "scenario_bear_pct", "scenario_bear_prob", "dont_panic_note",
]
REQUIRED_VERDICT_A = ["verdict", "reasoning", "conviction_score", "bull_case", "bear_case", "thesis_invalidation"]


class InputError(Exception):
    pass


def validate_verdict_a(va: dict) -> None:
    missing = [k for k in REQUIRED_VERDICT_A if va.get(k) in (None, "")]
    if missing:
        raise InputError(f"verdict_a is missing required field(s): {', '.join(missing)}")
    if va["verdict"] not in VERDICTS:
        raise InputError(f"verdict_a has invalid verdict {va['verdict']!r} (expected one of {sorted(VERDICTS)})")


def judge(va: dict, vb: dict, split_reason_text: str | None):
    """Returns (final_verdict, verdict_agreement, split_reason)."""
    a, b = va["verdict"], (vb or {}).get("verdict")
    if b is None:
        return a, None, None
    if b not in VERDICTS:
        raise InputError(f"verdict_b has invalid verdict {b!r}")
    note = (split_reason_text or "").strip() or None
    if a == b:
        ca, cb = va.get("conviction_score"), vb.get("conviction_score")
        if ca is not None and cb is not None and abs(ca - cb) >= _CONVICTION_GAP:
            return a, True, note or f"Both models say {a}, but confidence diverges: Claude {ca}/100 vs Gemini {cb}/100."
        return a, True, None
    return _SPLIT_OUTCOME[frozenset({a, b})], False, note or f"Claude says {a}, Gemini says {b}."


def build_payload(ticker: str, today: str, summary: dict, conv: dict, va: dict, vb: dict | None,
                  split_reason_text: str | None = None) -> dict:
    validate_verdict_a(va)
    final, agreement, split_reason = judge(va, vb, split_reason_text)
    payload = {"ticker": ticker, "analysis_date": today}
    payload.update({field: summary.get(key) for field, key in SUMMARY_FIELDS.items()})
    payload.update({field: va.get(field) for field in VERDICT_A_FIELDS})
    payload.update({
        "verdict": final,
        "conviction_score_raw": va.get("conviction_score"),
        "signal_convergence_score": conv.get("signal_convergence_score"),
        "convergence_details": json.dumps(conv.get("convergence_details")) if conv.get("convergence_details") is not None else None,
        "verdict_a": va["verdict"],
        "verdict_b": (vb or {}).get("verdict"),
        "verdict_agreement": agreement,
        "split_reason": split_reason,
    })
    if summary.get("data_conflicts") is not None:
        payload["data_conflicts"] = summary["data_conflicts"]
    if summary.get("earnings_date"):
        payload["earnings_date"] = summary["earnings_date"]
    for k in ("gemini_tokens_input", "gemini_tokens_output"):
        if (vb or {}).get(k) is not None:
            payload[k] = vb[k]
    return payload


def _load(path: str, required: bool = True):
    if not os.path.exists(path):
        if required:
            raise InputError(f"{path} not found — run the earlier step for this ticker first")
        return None
    with open(path) as f:
        if path.endswith(".txt"):
            return f.read()
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise InputError(f"{path} is not valid JSON: {e}")


def post(payload: dict, backend: str, secret: str, attempts: int = 3):
    import requests
    last = None
    for i in range(attempts):
        try:
            r = requests.post(f"{backend}/jobs/ingest-analysis", params={"x_job_secret": secret}, json=payload, timeout=60)
            if r.status_code < 500:
                return r.status_code, r.text
            last = f"HTTP {r.status_code}: {r.text[:300]}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"POST failed after {attempts} attempts: {last}")


def main(argv=None, tmp: str = "/tmp") -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--dry-run", action="store_true", help="print the payload, don't POST")
    args = ap.parse_args(argv)
    t = args.ticker.upper()
    try:
        payload = build_payload(
            t, date.today().isoformat(),
            _load(f"{tmp}/summary_{t}.json"), _load(f"{tmp}/convergence_{t}.json"),
            _load(f"{tmp}/verdict_a_{t}.json"), _load(f"{tmp}/verdict_b_{t}.json", required=False),
            _load(f"{tmp}/split_reason_{t}.txt", required=False),
        )
    except InputError as e:
        print(f"[{t}] NOT SAVED — {e}. Fix the file and re-run this script for {t}.")
        return 2
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0
    status, body = post(payload, os.environ["BACKEND_URL"], os.environ["JOB_SECRET"])
    tag = f"final={payload['verdict']} A={payload['verdict_a']} B={payload['verdict_b']} agreement={payload['verdict_agreement']}"
    if status == 409:
        print(f"[{t}] already exists (HTTP 409) — skipped. {tag}")
        return 0
    if status >= 300:
        print(f"[{t}] NOT SAVED — HTTP {status}: {body[:300]}")
        return 1
    print(f"[{t}] saved — HTTP {status}. {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
