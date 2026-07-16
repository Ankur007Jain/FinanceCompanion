"""
Ticker Correlation Matrix — deterministic statistical compute, no LLM involved.

Usage: python3 scripts/compute_correlations.py
Requires BACKEND_URL, ADMIN_SECRET, JOB_SECRET in the environment.

Methodology:
- Daily log returns, not simple % — standard for return correlation work.
- PARTIAL correlation, not raw: each ticker's returns are regressed against the
  S&P 500's returns first (simple OLS), and correlation is computed on the
  RESIDUALS. Two tickers that are both just "long the market" will show high raw
  correlation for a reason that has nothing to do with them — partialling out
  market beta isolates co-movement that isn't just shared market exposure, which
  is what a "ripple effect" claim actually needs to mean.
- Three windows (30d/90d/180d) — a single point estimate hides whether a
  relationship is stable or a recent regime shift. All three get stored; 90d is
  the "primary" window used for the significance test.
- Significance: a p-value per pair from the 90d window, then Benjamini-Hochberg
  FDR correction applied across ALL computed pairs (not Bonferroni — too
  conservative at this many comparisons, would suppress real signal along with
  noise). Only pairs that survive FDR correction are marked significant=True.
  With ~90 tracked tickers there are ~4,000 pairs; at an uncorrected p<0.05,
  ~200 of those would look "significant" by chance alone — surfacing those to
  chat as if they were real relationships would be exactly the kind of
  plausible-but-invented claim the rest of this app's hallucination guards
  exist to prevent.
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import date

import numpy as np
from scipy.stats import pearsonr


def log_returns(closes: dict[str, float]) -> dict[str, float]:
    """{date: close} (sorted or not) -> {date: log return}. First date has no
    prior close to compare against, so it's dropped."""
    dates = sorted(closes.keys())
    returns = {}
    for i in range(1, len(dates)):
        prev, cur = closes[dates[i - 1]], closes[dates[i]]
        if prev and cur and prev > 0 and cur > 0:
            returns[dates[i]] = float(np.log(cur / prev))
    return returns


def residualize(ticker_returns: dict[str, float], market_returns: dict[str, float]) -> dict[str, float]:
    """Regress ticker_returns on market_returns (simple OLS), return the residuals —
    the part of each day's return NOT explained by the market's own move that day.
    Needs at least 30 overlapping days for a stable beta estimate; returns {} below
    that rather than fitting a line through a handful of points."""
    common = sorted(set(ticker_returns) & set(market_returns))
    if len(common) < 30:
        return {}
    y = np.array([ticker_returns[d] for d in common])
    x = np.array([market_returns[d] for d in common])
    beta, alpha = np.polyfit(x, y, 1)
    predicted = alpha + beta * x
    resid = y - predicted
    return {d: float(r) for d, r in zip(common, resid)}


def pairwise_correlation(
    residuals_a: dict[str, float], residuals_b: dict[str, float], window: int, min_overlap: int = 20
) -> tuple[float, float, int] | None:
    """Pearson correlation + p-value over the most recent `window` overlapping
    trading days. None if fewer than min_overlap days of real overlap exist —
    a correlation computed on a handful of points is noise, not signal."""
    common = sorted(set(residuals_a) & set(residuals_b))[-window:]
    if len(common) < min_overlap:
        return None
    a = np.array([residuals_a[d] for d in common])
    b = np.array([residuals_b[d] for d in common])
    if np.std(a) == 0 or np.std(b) == 0:
        return None
    r, p = pearsonr(a, b)
    return float(r), float(p), len(common)


def benjamini_hochberg(p_values: list[float], alpha: float = 0.05) -> list[bool]:
    """Standard BH step-up FDR correction. Returns, in the ORIGINAL input order,
    which p-values survive at the given false-discovery rate."""
    n = len(p_values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: p_values[i])
    ranked = [p_values[i] for i in order]
    threshold_idx = -1
    for rank, p in enumerate(ranked, start=1):
        if p <= (rank / n) * alpha:
            threshold_idx = rank
    survives = [False] * n
    if threshold_idx > 0:
        for rank in range(threshold_idx):
            survives[order[rank]] = True
    return survives


def compute_correlation_matrix(
    closes: dict[str, dict[str, float]],
    market_closes: dict[str, float],
    windows: tuple[int, ...] = (30, 90, 180),
    min_overlap: int = 20,
) -> list[dict]:
    """Orchestrates the full pipeline for a universe of tickers. Returns one record
    per pair with ticker_a < ticker_b (alphabetized so each pair appears once)."""
    market_returns = log_returns(market_closes)

    residuals = {}
    for ticker, series in closes.items():
        r = residualize(log_returns(series), market_returns)
        if r:
            residuals[ticker] = r

    tickers = sorted(residuals.keys())
    pairs = []
    primary_window = 90 if 90 in windows else windows[-1]

    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            a, b = tickers[i], tickers[j]
            record = {"ticker_a": a, "ticker_b": b}
            primary = None
            for w in windows:
                result = pairwise_correlation(residuals[a], residuals[b], w, min_overlap)
                record[f"corr_{w}d"] = round(result[0], 4) if result else None
                if w == primary_window and result:
                    primary = result
            if primary:
                record["p_value_90d"] = round(primary[1], 6)
            else:
                record["p_value_90d"] = None
            pairs.append(record)

    p_values = [p["p_value_90d"] for p in pairs if p["p_value_90d"] is not None]
    testable = [p for p in pairs if p["p_value_90d"] is not None]
    survives = benjamini_hochberg(p_values)
    for p, sig in zip(testable, survives):
        p["significant"] = sig
    for p in pairs:
        p.setdefault("significant", False)

    return pairs


def main():
    import yfinance as yf

    backend = os.environ["BACKEND_URL"]
    admin_secret = os.environ["ADMIN_SECRET"]
    job_secret = os.environ["JOB_SECRET"]

    # 300 calendar days, not 200 — the 180-TRADING-day window needs a wider calendar
    # buffer since ~2/7 of calendar days are weekends (plus holidays). 200 calendar
    # days only yields ~140 trading days: enough for the 90d window, not the 180d one.
    url = f"{backend}/jobs/admin/closes?x_admin_secret={urllib.parse.quote(admin_secret)}&days=300"
    with urllib.request.urlopen(url, timeout=60) as r:
        closes = json.loads(r.read().decode())["closes"]

    print(f"# closes available for {len(closes)} tickers")
    if len(closes) < 2:
        print("FATAL: fewer than 2 tickers have price history — nothing to correlate.")
        sys.exit(1)

    try:
        sp5 = yf.Ticker("^GSPC").history(period="1y")
        market_closes = {d.strftime("%Y-%m-%d"): float(c) for d, c in sp5["Close"].items()}
    except Exception as e:
        print(f"FATAL: could not fetch S&P 500 history for market-beta adjustment ({e}).")
        sys.exit(1)

    pairs = compute_correlation_matrix(closes, market_closes)
    n_significant = sum(1 for p in pairs if p["significant"])
    print(f"# {len(pairs)} pairs computed, {n_significant} significant after FDR correction")

    payload = {
        "computed_date": date.today().isoformat(),
        "pairs": pairs,
    }
    with open("/tmp/correlations.json", "w") as f:
        json.dump(payload, f, indent=2)

    ingest_url = f"{backend}/jobs/ingest-correlations?x_job_secret={urllib.parse.quote(job_secret)}"
    req = urllib.request.Request(
        ingest_url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        print(json.loads(r.read().decode()))


if __name__ == "__main__":
    main()
