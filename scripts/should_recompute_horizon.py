"""
Horizon weekly pipeline — deterministic skip-check for the long-term/short-term horizon
judgment. Usage: python3 scripts/should_recompute_horizon.py TICKER
Reads /tmp/summary_{ticker}.json (this week's fundamentals snapshot, written by
nightly_fetch.py — reused as-is, same fields), /tmp/horizon_prior_{ticker}.json (the
fundamentals + trend behind the last computed judgment — absent if never computed), and
/tmp/fundamentals_trend_{ticker}.json (this week's self-derived trend, from
compute_fundamentals_trend.py). Writes
/tmp/horizon_skip_{ticker}.json: {"should_recompute": bool, "reason": "..."}.

Two trigger families:
- Snapshot deltas (revenue/earnings growth, margin, valuation, leverage, market cap,
  analyst consensus) — the original design, mirrors compute_signal_convergence.py.
- Trend STATE CHANGES (e.g. institutional ownership flips from STABLE to DISTRIBUTING).
  Deliberately keyed on change-of-state, not "is currently trending" — a steady
  multi-week trend would otherwise force a recompute every single week, defeating the
  whole point of the skip-check.
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

_TREND_FIELDS = [
    ("revenue_growth_trend", "Revenue growth"),
    ("earnings_growth_trend", "Earnings growth"),
    ("margin_trend_recent", "Margin"),
    ("inst_ownership_trend", "Institutional ownership"),
    ("insider_ownership_trend", "Insider ownership"),
]


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


def _trend_changed(prior: dict, trend: dict, field: str, label: str, reasons: list[str]) -> None:
    new_val = trend.get(field)
    if new_val is None:
        return  # not enough self-derived history yet to say anything new
    old_val = prior.get(field)
    if new_val != old_val:
        reasons.append(f"{label} trend changed: {old_val or 'unknown'} -> {new_val}.")


def should_recompute(now: dict, prior: dict | None, trend: dict, today: date | None = None) -> dict:
    """Pure decision function.
    `now`: this week's cheap fundamentals snapshot (nightly_fetch.py summary shape).
    `prior`: last computed judgment's snapshot (GET /jobs/admin/last-horizon shape), or
             None if never computed.
    `trend`: this week's self-derived trend classification (compute_fundamentals_trend.py
             output) — always available, independent of `prior`.
    """
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

    for field, label in _TREND_FIELDS:
        _trend_changed(prior, trend, field, label, reasons)

    result = {
        "should_recompute": bool(reasons),
        "reason": " ".join(reasons) if reasons else "No material change since last computed judgment — reused prior.",
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

    trend = {}
    trend_path = f"/tmp/fundamentals_trend_{ticker}.json"
    if os.path.exists(trend_path):
        with open(trend_path) as f:
            trend = json.load(f)

    result = should_recompute(now, prior, trend)

    with open(f"/tmp/horizon_skip_{ticker}.json", "w") as f:
        json.dump(result, f)

    print(f"[{ticker}] should_recompute={result['should_recompute']} — {result['reason']}")
