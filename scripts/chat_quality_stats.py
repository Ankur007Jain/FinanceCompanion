"""
Chat Quality Sentinel — fetches a recent sample of chatbot messages plus deterministic
aggregate stats for the daily sentinel agent to interpret.

Usage: python3 scripts/chat_quality_stats.py
Requires BACKEND_URL and ADMIN_SECRET in the environment.
Prints the stats JSON to stdout and writes /tmp/chat_quality.json.
"""
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime

backend = os.environ["BACKEND_URL"]
secret = os.environ["ADMIN_SECRET"]

url = f"{backend}/jobs/admin/chat-quality-sample?x_admin_secret={urllib.parse.quote(secret)}&days=1&limit=150"
with urllib.request.urlopen(url, timeout=30) as r:
    sample = json.loads(r.read().decode())["messages"]

# Deterministic aggregate stats only — hallucination/off-topic judgment needs language
# understanding and is left to the agent step, which reads the raw sample separately.
assistant_msgs = [m for m in sample if m["role"] == "assistant"]
empty_responses = [m for m in assistant_msgs if not (m["content"] or "").strip()]
model_counts: dict[str, int] = {}
for m in assistant_msgs:
    key = m.get("model_used") or "unknown"
    model_counts[key] = model_counts.get(key, 0) + 1

response_lengths = [len(m["content"]) for m in assistant_msgs if m["content"]]
avg_length = round(sum(response_lengths) / len(response_lengths), 0) if response_lengths else None

stats = {
    "total_messages": len(sample),
    "assistant_messages": len(assistant_msgs),
    "empty_assistant_responses": len(empty_responses),
    "model_usage": model_counts,
    "avg_assistant_response_chars": avg_length,
    "sample_window_start": min((m["created_at"] for m in sample), default=None),
    "sample_window_end": max((m["created_at"] for m in sample), default=None),
    "generated_at": datetime.utcnow().isoformat() + "Z",
}

with open("/tmp/chat_quality.json", "w") as f:
    json.dump(stats, f, indent=2)
print(json.dumps(stats, indent=2))

# Raw sample saved separately (not printed — can be large) for the agent step to read
# directly when it spot-checks individual transcripts.
with open("/tmp/chat_quality_sample.json", "w") as f:
    json.dump(sample, f, indent=2)
