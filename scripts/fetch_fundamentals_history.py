"""
Horizon weekly pipeline — fetch each ticker's own fundamentals history (revenue/earnings
growth, margin, ownership) from stock_analyses over the trailing N days.
Usage: python3 scripts/fetch_fundamentals_history.py TICKER1,TICKER2,... [days]
Writes /tmp/fundamentals_history_{ticker}.json for each ticker that has history.
Requires BACKEND_URL and ADMIN_SECRET in the environment.
"""
import sys, json, os, urllib.request, urllib.parse

tickers = sys.argv[1]
days = sys.argv[2] if len(sys.argv) > 2 else "180"
backend = os.environ["BACKEND_URL"]
secret = os.environ["ADMIN_SECRET"]

url = (f"{backend}/jobs/admin/fundamentals-history?x_admin_secret={urllib.parse.quote(secret)}"
       f"&tickers={urllib.parse.quote(tickers)}&days={days}")
try:
    with urllib.request.urlopen(url, timeout=15) as r:
        fundamentals = json.loads(r.read().decode()).get("fundamentals", {})
except Exception as e:
    print(f"Fundamentals history fetch failed ({e}) — trend signals unavailable this run.")
    fundamentals = {}

for t in tickers.split(","):
    t = t.strip().upper()
    hist = fundamentals.get(t)
    if hist:
        with open(f"/tmp/fundamentals_history_{t}.json", "w") as f:
            json.dump(hist, f)
        print(f"[{t}] fundamentals history: {len(hist)} days")
    else:
        print(f"[{t}] no fundamentals history yet")
