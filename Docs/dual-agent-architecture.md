# Dual-Agent Verdict Architecture

## Overview

FinanceCompanion's nightly analysis pipeline runs two independent AI models against the same raw market data and uses a judge agent to reconcile their verdicts. When both models agree, confidence is high. When they split, the system issues a conservative WATCH and surfaces the disagreement to the user.

---

## Why Two Models?

A single model can have systematic biases — it may consistently overweight certain signals, underweight geopolitical risk, or have training data gaps for specific sectors. Running two models from different providers (different architectures, different training data) means disagreements are meaningful signal rather than random noise.

| Single model | Dual model |
|---|---|
| One bias, unknown | Two biases, partially canceling |
| Confident errors invisible | Confident errors surface as splits |
| No cross-validation | Verdict only issued when both agree or judge synthesizes |

---

## Model Choice

| Role | Model | Provider | Why |
|------|-------|----------|-----|
| Agent A | `claude-sonnet-4-6` | Anthropic | Current production model, strong at structured reasoning |
| Agent B | `gemini-2.5-flash` | Google AI | Verified working, 0.91s latency, comparable benchmark scores on Finance Agent tasks |
| Judge | `claude-sonnet-4-6` | Anthropic | Sees both verdicts + reasoning, issues final verdict and flags splits |

> **Note:** `gemini-3.5-flash` is the target Agent B model (stronger peer to Sonnet 4.6) but was experiencing 503s due to post-launch demand at time of implementation. The model ID is a single variable — upgrade is a one-line change once the model stabilizes.

---

## Architecture

```
NIGHTLY GHA PIPELINE (per ticker)
─────────────────────────────────────────────────────────

Step 1   Fetch raw data from yfinance
         │
         ├── info_json    (company fundamentals, analyst data)
         ├── history_json (1-year daily OHLCV)
         ├── news_json    (raw news articles)
         └── calendar_json (earnings calendar)
         │
Step 1b  POST /jobs/ingest-snapshot → market_data_cache table
         (permanent audit trail — enables replay without re-fetching)
         │
Step 2   Compute signal convergence score (0–7)
         CONVICTION FLOOR: score < 5 → verdict must be WATCH
         │
Step 3   ┌──────────────────────────────────────────┐
         │  Fork: same raw data, two independent    │
         │  verdict calls in parallel               │
         └──────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  Claude Sonnet 4.6              Gemini 2.5 Flash
  Verdict A                      Verdict B
  (reasoning_a)                  (reasoning_b)
         │                              │
         └──────────────┬───────────────┘
                        ▼
Step 3c  Judge: Claude Sonnet 4.6
         Compares verdict_a vs verdict_b

         IF agree  → verdict = verdict_a, verdict_agreement = true
         IF split  → verdict = conservative (BUY/HOLD → WATCH, SELL stays),
                     verdict_agreement = false,
                     split_reason = key point of difference
         │
Step 4   POST /jobs/ingest-analysis → stock_analyses table
         Payload includes: verdict_a, verdict_b, verdict_agreement, split_reason
         │
Step 5   Print batch summary
```

---

## Agreement Logic

| Claude (A) | Gemini (B) | Final Verdict | Agreement |
|------------|-----------|--------------|-----------|
| BUY | BUY | BUY | ✅ true |
| HOLD | HOLD | HOLD | ✅ true |
| SELL | SELL | SELL | ✅ true |
| WATCH | anything | WATCH | ✅ true (WATCH is always safe) |
| BUY | HOLD | WATCH | ⚠️ false |
| BUY | SELL | WATCH | ⚠️ false — strong signal |
| HOLD | SELL | WATCH | ⚠️ false |
| SELL | BUY | WATCH | ⚠️ false — strong signal |

---

## Database Schema

New columns added to `stock_analyses` (migration in `main.py`):

```sql
verdict_a         VARCHAR   -- Claude Sonnet 4.6 raw verdict
verdict_b         VARCHAR   -- Gemini 2.5 Flash raw verdict
verdict_agreement BOOLEAN   -- true = both agree, false = split
split_reason      TEXT      -- populated only when verdict_a != verdict_b
```

All four columns are nullable — backward compatible with analyses ingested before this feature.

---

## API Changes

### `POST /jobs/ingest-snapshot` *(new — Phase 0)*

Saves raw yfinance data before verdict agents run. Called by GHA Step 1b.

```json
{
  "ticker": "NVDA",
  "cache_date": "2026-06-23",
  "info_json": "{...}",
  "history_json": "[{\"Date\":\"2026-06-20\",\"Close\":127.4,...}]",
  "news_json": "[{\"title\":\"...\"}]",
  "calendar_json": "{\"Earnings Date\":[\"2026-08-20\"]}"
}
```

Table: `market_data_cache` (ticker + cache_date composite PK, upserts on conflict)

### `POST /jobs/ingest-analysis` *(extended — Phase 1)*

Now accepts and persists dual-agent fields:

```json
{
  "ticker": "NVDA",
  "verdict": "BUY",
  "verdict_a": "BUY",
  "verdict_b": "BUY",
  "verdict_agreement": true,
  "split_reason": null,
  ...existing fields...
}
```

### `GET /analysis/digest` *(extended — Phase 1)*

`StockAnalysisOut` now includes `verdict_a`, `verdict_b`, `verdict_agreement`, `split_reason` — available to the frontend for badge rendering.

---

## Frontend Badge (Phase 3)

Stock card row shows a confidence badge based on `verdict_agreement`:

```
NVDA  Nvidia Corp          BUY  ●●●
$127.40  ▲ 2.1%
✅ Both models agree — High confidence

INTC  Intel Corp           WATCH  ●●○
$21.30  ▼ 0.8%
⚠️ Models split: Claude=HOLD · Gemini=SELL
   Conservative WATCH issued
```

---

## Implementation Phases

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 0** | ✅ Merged (PR #27) | Wire up `market_data_cache` — save raw snapshot before verdict |
| **Phase 1** | 🔁 In review (PR #28) | Add `verdict_a/b/agreement/split_reason` DB fields, schema, migration |
| **Phase 2** | ⏳ Pending | Update GHA nightly prompt — add Gemini call + judge logic |
| **Phase 3** | ⏳ Pending | Frontend badge — show ✅ / ⚠️ on stock card |

---

## Cost Estimate

Gemini 2.5 Flash pricing: $0.10/1M input · $0.40/1M output

| | Per ticker | 28 tickers/night | Per month |
|---|---|---|---|
| Input (~800 tokens) | $0.00008 | $0.0022 | ~$0.07 |
| Output (~400 tokens) | $0.00016 | $0.0045 | ~$0.14 |
| **Total** | | **~$0.007/night** | **~$0.21/month** |

Effectively free. The judge call (Claude Sonnet) uses existing Anthropic quota.

---

## Gemini API Setup

- Provider: Google AI Studio ([aistudio.google.com](https://aistudio.google.com))
- SDK: `google-genai` (new, replaces deprecated `google-generativeai`)
- Key location: `backend/.env` → `GEMINI_API_KEY`
- GitHub secret: `GEMINI_API_KEY` in Production environment
- Billing: Prepay ($10 credit loaded Jun 23 2026) — paid tier unlocks 150+ RPM

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
resp = client.models.generate_content(
    model="models/gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=2048,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    ),
)
```

> `thinking_budget=0` disables chain-of-thought to avoid token truncation on JSON output.

---

## Retry Strategy

Both Agent B (Gemini) and the judge call should retry on 503:

```python
for attempt in range(3):
    try:
        resp = client.models.generate_content(...)
        break
    except Exception as e:
        if "503" in str(e) and attempt < 2:
            time.sleep(30)
            continue
        # fallback: use verdict_a as final, set verdict_agreement=None
        break
```

If Gemini is unavailable after retries, the pipeline falls back to Claude-only (existing behavior) and leaves `verdict_b` and `verdict_agreement` as null — no data loss.
