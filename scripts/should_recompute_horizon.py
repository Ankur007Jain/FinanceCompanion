"""
Nightly pipeline — deterministic skip-check for the long-term/short-term horizon judgment.
Usage: python3 scripts/should_recompute_horizon.py TICKER
Reads /tmp/summary_{ticker}.json (tonight's fundamentals, from nightly_fetch.py) and
/tmp/horizon_prior_{ticker}.json (last computed judgment + the fundamentals it was based
on, from nightly_fetch_horizon.py — absent if never computed). Writes
/tmp/horizon_skip_{ticker}.json: {"should_recompute": bool, "reason": "..."}.

Mirrors compute_signal_convergence.py's pattern: a cheap, deterministic pre-check so the
LLM only pays for fresh horizon reasoning (a 401k/retirement-fund-style 1-5yr holding
judgment) when something that would actually change that judgment has moved — not every
night just because the nightly run happened to touch this ticker.
"""
import json
import os
import sys
from datetime import date

STALENESS_DAYS = 90
REVENUE_GROWTH_THRESHOLD = 0.05
EARNINGS_GROWTH_THRESHOLD = 0.10
PROFIT_MARGIN_THRESHOLD = 0.05
PE_FORWARD_RELATIVE_THRESHOLD = 0.20
DEBT_TO_EQUITY_RELATIVE_THRESHOLD = 0.20
MARKET_CAP_RELATIVE_THRESHOLD = 0.20


def _pct_moved(prior: dict, now: dict, field: str, threshold_abs: float, label: str, reasons: list[str]) -> None:
    old, new = prior.get(field), now.get(field)
    if old is None or new is None:
        return
    if abs(new - old) >= threshold_abs:
        reasons.append(f"{label} moved {old:.1%} -> {new:.1%} (>= {threshold_abs:.0%} threshold).")


def _relative_moved(prior: dict, now: dict, field: str, threshold_rel: float, label: str, reasons: list[str]) -> None:
    old, new = prior.get(field), now.get(field)
    if old is None or new is None:
        return
    if old == 0:
        if new != 0:
            reasons.append(f"{label} moved {old:.2f} -> {new:.2f} (from a zero baseline).")
        return
    rel = abs(new - old) / abs(old)
    if rel >= threshold_rel:
        reasons.append(f"{label} moved {old:.2f} -> {new:.2f} ({rel:.0%} relative change, >= {threshold_rel:.0%} threshold).")


def should_recompute(now: dict, prior: dict | None, today: date | None = None) -> dict:
    """Pure decision function — `now` is tonight's summary JSON dict (nightly_fetch.py
    shape: keys like revenue_growth, pe_forward, analyst, ...), `prior` is the last
    computed horizon snapshot (GET /jobs/admin/last-horizon shape) or None if never
    computed."""
    today = today or date.today()

    if not prior:
        return {"should_recompute": True, "reason": "No prior horizon judgment on record."}

    reasons: list[str] = []

    last_computed = prior.get("time_horizon_last_computed")
    if last_computed:
        days_since = (today - date.fromisoformat(last_computed)).days
        if days_since > STALENESS_DAYS:
            reasons.append(f"Staleness safety net: {days_since} days since last computed (>{STALENESS_DAYS}).")

    old_consensus, new_consensus = prior.get("analyst_consensus"), now.get("analyst")
    if old_consensus and new_consensus and old_consensus.upper() != new_consensus.upper():
        reasons.append(f"Analyst consensus changed: {old_consensus} -> {new_consensus}.")

    _pct_moved(prior, now, "revenue_growth", REVENUE_GROWTH_THRESHOLD, "Revenue growth", reasons)
    _pct_moved(prior, now, "earnings_growth", EARNINGS_GROWTH_THRESHOLD, "Earnings growth", reasons)
    _pct_moved(prior, now, "profit_margin", PROFIT_MARGIN_THRESHOLD, "Profit margin", reasons)
    _relative_moved(prior, now, "pe_forward", PE_FORWARD_RELATIVE_THRESHOLD, "Forward P/E", reasons)
    _relative_moved(prior, now, "debt_to_equity", DEBT_TO_EQUITY_RELATIVE_THRESHOLD, "Debt/equity", reasons)
    _relative_moved(prior, now, "market_cap", MARKET_CAP_RELATIVE_THRESHOLD, "Market cap", reasons)

    result = {
        "should_recompute": bool(reasons),
        "reason": " ".join(reasons) if reasons else "No material fundamentals change since last computed judgment — reused prior.",
    }
    if not result["should_recompute"]:
        result["reused_fit"] = prior.get("time_horizon_fit")
        result["reused_reasoning"] = prior.get("time_horizon_reasoning")
    return result


if __name__ == "__main__":
    ticker = sys.argv[1]

    with open(f"/tmp/summary_{ticker}.json") as f:
        now = json.load(f)

    prior = None
    prior_path = f"/tmp/horizon_prior_{ticker}.json"
    if os.path.exists(prior_path):
        with open(prior_path) as f:
            prior = json.load(f)

    result = should_recompute(now, prior)

    with open(f"/tmp/horizon_skip_{ticker}.json", "w") as f:
        json.dump(result, f)

    print(f"[{ticker}] should_recompute={result['should_recompute']} — {result['reason']}")
