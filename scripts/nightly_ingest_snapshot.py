"""
Nightly pipeline — Step 1b: POST the raw snapshot fetched by nightly_fetch.py to the backend.
Usage: python3 scripts/nightly_ingest_snapshot.py TICKER
Requires BACKEND_URL and JOB_SECRET in the environment.
"""
import sys, json, subprocess, os
from datetime import date

ticker = sys.argv[1]
today = str(date.today())
backend = os.environ["BACKEND_URL"]
secret = os.environ["JOB_SECRET"]

with open(f"/tmp/raw_{ticker}.json") as f:
    raw = json.load(f)

payload = json.dumps({
    "ticker": ticker,
    "cache_date": today,
    "info_json": raw["info_json"],
    "history_json": raw["history_json"],
    "news_json": raw["news_json"],
    "calendar_json": raw["calendar_json"],
})

r = subprocess.run(
    ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
     "-X", "POST", f"{backend}/jobs/ingest-snapshot?x_job_secret={secret}",
     "-H", "Content-Type: application/json",
     "-d", payload],
    capture_output=True, text=True
)
print(f"[{ticker}] Snapshot saved — HTTP {r.stdout.strip()}")
