"""
Nightly pipeline — Step 1c: fetch per-ticker stock memory (lessons from past analyses/reports).
Usage: python3 scripts/nightly_fetch_memory.py TICKER1,TICKER2,...
Writes /tmp/memory_{ticker}.txt for each ticker that has a memory; skips those without.
Requires BACKEND_URL and ADMIN_SECRET in the environment.
"""
import sys, json, os, urllib.request, urllib.parse

tickers = sys.argv[1]
backend = os.environ["BACKEND_URL"]
secret = os.environ["ADMIN_SECRET"]

url = f"{backend}/jobs/admin/memories?x_admin_secret={urllib.parse.quote(secret)}&tickers={urllib.parse.quote(tickers)}"
try:
    with urllib.request.urlopen(url, timeout=15) as r:
        memories = json.loads(r.read().decode()).get("memories", {})
except Exception as e:
    print(f"Memory fetch failed ({e}) — verdicts will run without past lessons.")
    memories = {}

for t in tickers.split(","):
    t = t.strip().upper()
    mem = memories.get(t)
    if mem:
        with open(f"/tmp/memory_{t}.txt", "w") as f:
            f.write(mem)
        print(f"[{t}] memory saved ({len(mem)} chars)")
    else:
        print(f"[{t}] no memory yet")
