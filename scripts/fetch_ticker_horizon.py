"""
Shared by both pipelines — fetch each ticker's current long-term/short-term horizon
judgment (TickerHorizon) + the fundamentals/trend behind it.
Usage: python3 scripts/fetch_ticker_horizon.py TICKER1,TICKER2,...
Writes /tmp/horizon_prior_{ticker}.json for each ticker that has a computed judgment;
tickers with none (never computed) get no file. Two callers, two meanings for that file:
- horizon-weekly.yml: should_recompute_horizon.py treats a missing file as "always
  recompute" — this IS the "prior" it diffs against.
- nightly.yml: reads it as fixed, read-only background context (interest coverage,
  analyst rating momentum, 3yr revenue CAGR, the time_horizon_fit itself) for the
  near-term verdict. A missing file just means no weekly judgment exists yet — treat
  as unknown, not a red flag, especially before horizon-weekly.yml's first real run.
Requires BACKEND_URL and ADMIN_SECRET in the environment.
"""
import sys, json, os, urllib.request, urllib.parse

tickers = sys.argv[1]
backend = os.environ["BACKEND_URL"]
secret = os.environ["ADMIN_SECRET"]

url = f"{backend}/jobs/admin/last-horizon?x_admin_secret={urllib.parse.quote(secret)}&tickers={urllib.parse.quote(tickers)}"
try:
    with urllib.request.urlopen(url, timeout=15) as r:
        horizons = json.loads(r.read().decode()).get("horizons", {})
except Exception as e:
    print(f"Horizon fetch failed ({e}) — every ticker will recompute this run.")
    horizons = {}

for t in tickers.split(","):
    t = t.strip().upper()
    prior = horizons.get(t)
    if prior:
        with open(f"/tmp/horizon_prior_{t}.json", "w") as f:
            json.dump(prior, f)
        print(f"[{t}] horizon on record: {prior['time_horizon_fit']} (computed {prior['time_horizon_last_computed']})")
    else:
        print(f"[{t}] no horizon on record yet")
