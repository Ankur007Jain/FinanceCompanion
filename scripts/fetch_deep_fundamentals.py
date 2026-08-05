"""
Horizon weekly pipeline — Phase B: deeper long-term fundamentals, fetched from yfinance
ONLY for tickers should_recompute_horizon.py flagged (income_stmt/balance_sheet/
upgrades_downgrades are heavier calls than the cheap nightly summary, so this must stay
gated — that's the whole point of the skip-check).

Usage: python3 scripts/fetch_deep_fundamentals.py TICKER
Writes /tmp/deep_fundamentals_{ticker}.json:
{"revenue_cagr_3y": float|null, "margin_trend_3y": str|null,
 "interest_coverage_ratio": float|null, "analyst_rating_changes_90d": int|null}

Row/column labels (Total Revenue, EBIT, Interest Expense, Action) verified against a
live yfinance 1.5.2 pull for AAPL — yfinance's exact label set has drifted across
versions before, so if this starts returning all-null for every ticker, check
`t.income_stmt.index` / `t.upgrades_downgrades['Action'].unique()` first.

Margin and interest-coverage divide two income_stmt ROWS, each a pandas Series indexed
by fiscal-period date — dividing two Series aligns by that date index automatically, so
a period where one row is NaN (real: Apple's income_stmt has NaN Interest Expense for
its 2 most recent fiscal years) correctly drops out via .dropna() instead of silently
propagating NaN into the stored ratio (NaN is truthy in Python — `if x:` doesn't catch it).
"""
import sys
import json
from datetime import datetime, timedelta

import yfinance as yf

MARGIN_TREND_THRESHOLD = 0.02  # 2pp

ticker = sys.argv[1]
t = yf.Ticker(ticker)

revenue_cagr_3y = None
margin_trend_3y = None
interest_coverage_ratio = None
analyst_rating_changes_90d = None

try:
    revenue = t.income_stmt.loc["Total Revenue"].dropna()
    if len(revenue) >= 2:
        years_span = min(3, len(revenue) - 1)
        newest, oldest = float(revenue.iloc[0]), float(revenue.iloc[years_span])
        if oldest > 0:
            revenue_cagr_3y = round((newest / oldest) ** (1 / years_span) - 1, 4)
except Exception as e:
    print(f"[{ticker}] revenue_cagr_3y failed: {e}")

try:
    inc = t.income_stmt
    margin = (inc.loc["EBIT"] / inc.loc["Total Revenue"]).dropna()
    if len(margin) >= 2:
        span = min(3, len(margin) - 1)
        delta = float(margin.iloc[0]) - float(margin.iloc[span])
        margin_trend_3y = (
            "EXPANDING" if delta >= MARGIN_TREND_THRESHOLD else
            "CONTRACTING" if delta <= -MARGIN_TREND_THRESHOLD else
            "STABLE"
        )
except Exception as e:
    print(f"[{ticker}] margin_trend_3y failed: {e}")

try:
    inc = t.income_stmt
    coverage = (inc.loc["EBIT"] / inc.loc["Interest Expense"].abs()).replace([float("inf"), float("-inf")], None).dropna()
    if len(coverage) >= 1:
        interest_coverage_ratio = round(float(coverage.iloc[0]), 2)
except Exception as e:
    print(f"[{ticker}] interest_coverage_ratio failed: {e}")

try:
    ud = t.upgrades_downgrades
    if ud is not None and not ud.empty:
        cutoff = datetime.now() - timedelta(days=90)
        recent = ud[ud.index >= cutoff]
        analyst_rating_changes_90d = int((recent["Action"] == "up").sum()) - int((recent["Action"] == "down").sum())
except Exception as e:
    print(f"[{ticker}] analyst_rating_changes_90d failed: {e}")

result = {
    "revenue_cagr_3y": revenue_cagr_3y,
    "margin_trend_3y": margin_trend_3y,
    "interest_coverage_ratio": interest_coverage_ratio,
    "analyst_rating_changes_90d": analyst_rating_changes_90d,
}

with open(f"/tmp/deep_fundamentals_{ticker}.json", "w") as f:
    json.dump(result, f)

print(f"[{ticker}] deep fundamentals: {result}")
