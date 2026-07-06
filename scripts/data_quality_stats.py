"""
Data Quality Sentinel — fetches per-date NULL rates and missing-ticker stats
for the daily sentinel agent to interpret.

Usage: python3 scripts/data_quality_stats.py
Requires BACKEND_URL and ADMIN_SECRET in the environment.
Prints the stats JSON to stdout and writes /tmp/data_quality.json.
"""
import json
import os
import urllib.request
import urllib.parse

backend = os.environ["BACKEND_URL"]
secret = os.environ["ADMIN_SECRET"]

url = f"{backend}/jobs/admin/data-quality?x_admin_secret={urllib.parse.quote(secret)}&days=7"
with urllib.request.urlopen(url, timeout=30) as r:
    stats = json.loads(r.read().decode())

with open("/tmp/data_quality.json", "w") as f:
    json.dump(stats, f, indent=2)
print(json.dumps(stats, indent=2))
