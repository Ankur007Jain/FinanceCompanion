"""
Nightly pipeline — fetch each ticker's last-computed long-term/short-term horizon
judgment + the fundamentals it was based on.
Usage: python3 scripts/nightly_fetch_horizon.py TICKER1,TICKER2,...
Writes /tmp/horizon_prior_{ticker}.json for each ticker that has a prior judgment;
tickers with no prior judgment (never computed) get no file — should_recompute_horizon.py
treats a missing file as "always recompute."
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
        print(f"[{t}] prior horizon: {prior['time_horizon_fit']} (computed {prior['time_horizon_last_computed']})")
    else:
        print(f"[{t}] no prior horizon — will compute fresh")
