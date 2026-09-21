"""
Verdict Scorecard — deterministic outcome math for the weekly scorecard agent.
Replays every verdict from the last N days against actual subsequent prices.

Usage: python3 scripts/scorecard_compute.py
Requires BACKEND_URL and ADMIN_SECRET in the environment.
Prints a JSON report to stdout and writes /tmp/scorecard.json.
Exits non-zero if price data is unavailable — an empty scorecard must never be
published as if it were a real result.

Methodology (v1, close-only — conservative):
- Forward returns measured at 5 and 21 trading days after the analysis date.
- BUY target/stop resolution uses daily closes (not intraday highs/lows), so
  "hit" is understated rather than overstated.
- Analyses newer than 7 calendar days are excluded (not enough forward data).
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timedelta


def conviction_band(c):
    if c is None:
        return "unknown"
    return "70+" if c >= 70 else "50-69" if c >= 50 else "<50"


def range_band(rp):
    if rp is None:
        return "unknown"
    return "70+" if rp >= 70 else "50-69" if rp >= 50 else "<50"


def compute_report(analyses: list[dict], closes: dict[str, dict[str, float]], today: date | None = None) -> dict:
    """Pure outcome math — analyses from /jobs/admin/verdict-history, closes as
    {ticker: {iso_date: close}}. Testable without network access."""
    today = today or date.today()
    cutoff = today - timedelta(days=7)
    analyses = [a for a in analyses if date.fromisoformat(a["date"]) < cutoff]

    def forward_prices(ticker: str, from_date: str):
        series = closes.get(ticker, {})
        return [(d, p) for d, p in sorted(series.items()) if d > from_date]

    by_verdict = defaultdict(list)   # verdict -> list of (ret5, ret21, date)
    by_band = defaultdict(list)      # conviction band (BUY only) -> 5d returns
    by_score = defaultdict(list)     # signal-score bucket (BUY only) -> (ret5, ret21, date)
    by_range = defaultdict(list)     # 52w-range-position band (BUY only) -> (ret5, ret21, date)
    by_entry_quality = defaultdict(list)  # GREAT/FAIR/WAIT the agent assigned at issue time
    by_vs_entry = defaultdict(list)  # price at issue vs the agent's own entry_target
    by_gate = defaultdict(list)      # score>=7 & range<70 vs the rest (BUY only)
    day_rets = defaultdict(lambda: ([], []))  # date -> (all ret5s, all ret21s), every verdict
    buy_resolutions = defaultdict(int)
    failures = []

    for a in analyses:
        fwd = forward_prices(a["ticker"], a["date"])
        if len(fwd) < 5 or not a["price"]:
            continue
        ret5 = (fwd[4][1] - a["price"]) / a["price"] * 100
        ret21 = (fwd[20][1] - a["price"]) / a["price"] * 100 if len(fwd) >= 21 else None
        by_verdict[a["verdict"]].append((ret5, ret21, a["date"]))
        day_rets[a["date"]][0].append(ret5)
        if ret21 is not None:
            day_rets[a["date"]][1].append(ret21)

        if a["verdict"] == "BUY":
            by_band[conviction_band(a["conviction"])].append(ret5)
            sc, rp = a.get("signal_score"), a.get("range_pos")
            by_score["unknown" if sc is None else ">=7" if sc >= 7 else "<7"].append((ret5, ret21, a["date"]))
            by_range[range_band(rp)].append((ret5, ret21, a["date"]))
            by_entry_quality[a.get("entry_quality") or "unknown"].append((ret5, ret21, a["date"]))
            et = a.get("entry_target")
            vs = "unknown" if not et else "within 1% of entry_target (or below)" if (a["price"] - et) / et * 100 <= 1 else "more than 1% above entry_target"
            by_vs_entry[vs].append((ret5, ret21, a["date"]))
            passes = sc is not None and rp is not None and sc >= 7 and rp < 70
            by_gate["score>=7 & range<70" if passes else "everything else"].append((ret5, ret21, a["date"]))
            # Which did a close cross first within 21 trading days: exit target or stop?
            resolution = "unresolved"
            if a["exit_target"] and a["stop_loss"]:
                for _, p in fwd[:21]:
                    if p >= a["exit_target"]:
                        resolution = "target_hit"; break
                    if p <= a["stop_loss"]:
                        resolution = "stopped_out"; break
            buy_resolutions[resolution] += 1
            if resolution == "stopped_out" or ret5 < -8:
                failures.append({
                    "ticker": a["ticker"], "date": a["date"], "conviction": a["conviction"],
                    "price": a["price"], "stop_loss": a["stop_loss"], "ret5_pct": round(ret5, 1),
                    "resolution": resolution,
                })

    # Excess return vs. the same-day average across ALL tracked tickers. Absolute
    # returns conflate stock selection with market regime: WATCH is ~1,900 names and
    # behaves like the market, while BUY is a concentrated ~5/day basket — so in a
    # sector pullback BUY looks terrible vs. WATCH even if it beat the universe.
    base5 = {d: sum(v[0]) / len(v[0]) for d, v in day_rets.items() if v[0]}
    base21 = {d: sum(v[1]) / len(v[1]) for d, v in day_rets.items() if v[1]}

    def summarize(triples):
        r5 = [p[0] for p in triples]
        r21 = [p[1] for p in triples if p[1] is not None]
        x5 = [p[0] - base5[p[2]] for p in triples]
        x21 = [p[1] - base21[p[2]] for p in triples if p[1] is not None and p[2] in base21]
        return {
            "n": len(triples),
            "avg_ret_5d_pct": round(sum(r5) / len(r5), 2) if r5 else None,
            "win_rate_5d_pct": round(100 * sum(1 for x in r5 if x > 0) / len(r5), 1) if r5 else None,
            "avg_ret_21d_pct": round(sum(r21) / len(r21), 2) if r21 else None,
            "avg_excess_5d_pct": round(sum(x5) / len(x5), 2) if x5 else None,
            "avg_excess_21d_pct": round(sum(x21) / len(x21), 2) if x21 else None,
        }

    return {
        "generated": datetime.utcnow().isoformat() + "Z",
        "verdicts_evaluated": sum(len(v) for v in by_verdict.values()),
        "by_verdict": {v: summarize(pairs) for v, pairs in sorted(by_verdict.items())},
        "buy_by_conviction_band": {
            b: {"n": len(rets), "avg_ret_5d_pct": round(sum(rets) / len(rets), 2)}
            for b, rets in sorted(by_band.items())
        },
        "buy_by_signal_score": {k: summarize(v) for k, v in sorted(by_score.items())},
        "buy_by_range_position": {k: summarize(v) for k, v in sorted(by_range.items())},
        "buy_by_entry_quality": {k: summarize(v) for k, v in sorted(by_entry_quality.items())},
        "buy_by_price_vs_entry_target": {k: summarize(v) for k, v in sorted(by_vs_entry.items())},
        "buy_by_gate": {k: summarize(v) for k, v in sorted(by_gate.items())},
        "buy_target_vs_stop": dict(buy_resolutions),
        "notable_failures": sorted(failures, key=lambda f: f["ret5_pct"])[:15],
    }


def main():
    import yfinance as yf

    backend = os.environ["BACKEND_URL"]
    secret = os.environ["ADMIN_SECRET"]
    url = f"{backend}/jobs/admin/verdict-history?x_admin_secret={urllib.parse.quote(secret)}&days=45"
    with urllib.request.urlopen(url, timeout=30) as r:
        analyses = json.loads(r.read().decode())["analyses"]

    tickers = sorted({a["ticker"] for a in analyses})
    print(f"# {len(analyses)} verdicts across {len(tickers)} tickers")

    closes: dict[str, dict[str, float]] = {}
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="3mo")
            if len(hist):
                closes[t] = {d.strftime("%Y-%m-%d"): float(c) for d, c in hist["Close"].items()}
        except Exception as e:
            print(f"# {t}: price fetch failed ({e}) — skipped")

    if tickers and len(closes) < len(tickers) * 0.5:
        print(f"FATAL: price data available for only {len(closes)}/{len(tickers)} tickers "
              f"(likely rate-limited). Refusing to publish a hollow scorecard — rerun later.")
        sys.exit(1)

    report = compute_report(analyses, closes)
    with open("/tmp/scorecard.json", "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
