"""
Nightly pipeline — deterministic signal convergence score.
Usage: python3 scripts/compute_signal_convergence.py TICKER
Reads /tmp/summary_{ticker}.json (written by nightly_fetch.py) and writes
/tmp/convergence_{ticker}.json: {"signal_convergence_score": 0-10, "convergence_details": {...}}.

Computed here (not by the LLM) so conviction_score can be calibrated against a signal
that the model generating conviction_score cannot itself inflate. Thresholds match the
10-signal spec formerly handed to the LLM as prose in nightly.yml Step 2.
"""
import sys, json
from datetime import date

ticker = sys.argv[1]

with open(f"/tmp/summary_{ticker}.json") as f:
    d = json.load(f)


def _days_to_earnings(earnings_date):
    if not earnings_date:
        return None
    try:
        return (date.fromisoformat(str(earnings_date)) - date.today()).days
    except ValueError:
        return None


price = d.get("price")
ma50 = d.get("ma50")
support_20d = d.get("support_20d")
sp500_day_chg = d.get("sp500_day_chg")
relative_strength_1d = d.get("relative_strength_1d")
days_to_earnings = _days_to_earnings(d.get("earnings_date"))

signals = {
    "oversold_rsi":          d.get("rsi") is not None and d["rsi"] < 50,
    "near_52w_low":          d.get("range_pct") is not None and d["range_pct"] < 30,
    "analyst_upside_15pct":  d.get("upside_pct") is not None and d["upside_pct"] >= 15,
    "no_binary_risk":        days_to_earnings is None or days_to_earnings > 7,
    "positive_fcf":          d.get("free_cashflow") is not None and d["free_cashflow"] > 0,
    "institutional_backing": d.get("inst_ownership_pct") is not None and d["inst_ownership_pct"] >= 0.50,
    "price_stabilizing":     ma50 is None or (price is not None and price >= ma50),
    "near_support":          price is not None and support_20d is not None and price <= support_20d * 1.03,
    "sector_outperforming":  relative_strength_1d is not None and relative_strength_1d > 0,
    "sp500_tailwind":        sp500_day_chg is not None and sp500_day_chg > 0,
}

result = {
    "signal_convergence_score": sum(signals.values()),
    "convergence_details": signals,
}

with open(f"/tmp/convergence_{ticker}.json", "w") as f:
    json.dump(result, f)

print(f"[{ticker}] Signal convergence: {result['signal_convergence_score']}/10 {signals}")
