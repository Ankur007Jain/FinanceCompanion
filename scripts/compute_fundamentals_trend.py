"""
Horizon weekly pipeline — Phase A: self-derived fundamentals trend, computed purely from
a ticker's own accumulated stock_analyses history (fetch_fundamentals_history.py), zero
new external API calls. This is what fixes the core weakness of a snapshot-only judgment:
a single point-in-time revenue_growth number can't tell "steady 15% grower" from "growth
cratering from 40% to 15%" — comparing the earliest and latest values in the window can.

Usage: python3 scripts/compute_fundamentals_trend.py TICKER
Reads /tmp/fundamentals_history_{ticker}.json, writes /tmp/fundamentals_trend_{ticker}.json.
"""
import json
import sys

REVENUE_GROWTH_TREND_THRESHOLD = 0.03  # 3pp
MARGIN_TREND_THRESHOLD = 0.02          # 2pp
OWNERSHIP_TREND_THRESHOLD = 0.01       # 1pp


def _first_last(history: dict, field: str):
    """Earliest and latest non-null values for `field`, by date key. None if <2 points."""
    points = [(d, v[field]) for d, v in history.items() if v.get(field) is not None]
    if len(points) < 2:
        return None
    points.sort(key=lambda p: p[0])
    return points[0][1], points[-1][1]


def _classify(delta: float, threshold: float, up: str, down: str, flat: str) -> str:
    if delta >= threshold:
        return up
    if delta <= -threshold:
        return down
    return flat


def compute_trend(history: dict) -> dict:
    """`history` is {date_iso: {revenue_growth, earnings_growth, profit_margin,
    inst_ownership_pct, insider_ownership_pct}}, as returned by
    GET /jobs/admin/fundamentals-history. Returns a trend classification per field —
    None where there isn't yet enough history to say."""
    rg = _first_last(history, "revenue_growth")
    eg = _first_last(history, "earnings_growth")
    pm = _first_last(history, "profit_margin")
    inst = _first_last(history, "inst_ownership_pct")
    ins = _first_last(history, "insider_ownership_pct")

    return {
        "revenue_growth_trend": _classify(rg[1] - rg[0], REVENUE_GROWTH_TREND_THRESHOLD,
                                           "ACCELERATING", "DECELERATING", "STABLE") if rg else None,
        "earnings_growth_trend": _classify(eg[1] - eg[0], REVENUE_GROWTH_TREND_THRESHOLD,
                                            "ACCELERATING", "DECELERATING", "STABLE") if eg else None,
        "margin_trend_recent": _classify(pm[1] - pm[0], MARGIN_TREND_THRESHOLD,
                                          "EXPANDING", "CONTRACTING", "STABLE") if pm else None,
        "inst_ownership_trend": _classify(inst[1] - inst[0], OWNERSHIP_TREND_THRESHOLD,
                                           "ACCUMULATING", "DISTRIBUTING", "STABLE") if inst else None,
        "insider_ownership_trend": _classify(ins[1] - ins[0], OWNERSHIP_TREND_THRESHOLD,
                                              "INCREASING", "DECREASING", "STABLE") if ins else None,
    }


if __name__ == "__main__":
    ticker = sys.argv[1]
    try:
        with open(f"/tmp/fundamentals_history_{ticker}.json") as f:
            history = json.load(f)
    except FileNotFoundError:
        history = {}

    result = compute_trend(history)

    with open(f"/tmp/fundamentals_trend_{ticker}.json", "w") as f:
        json.dump(result, f)

    print(f"[{ticker}] fundamentals trend: {result}")
