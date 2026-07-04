"""
Nightly pipeline — Step 3b: Gemini's independent verdict (Verdict B).
Usage: python3 scripts/nightly_verdict_b.py TICKER
Reads /tmp/summary_{ticker}.json (written by nightly_fetch.py) and writes /tmp/verdict_b_{ticker}.json.
Requires GEMINI_API_KEY in the environment; writes {"verdict": None} if unavailable.
"""
import sys, json, os, re, time
from google import genai
from google.genai import types

ticker = sys.argv[1]
api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    print(f"[{ticker}] GEMINI_API_KEY not set — skipping Verdict B")
    with open(f"/tmp/verdict_b_{ticker}.json", "w") as f:
        json.dump({"verdict": None}, f)
    raise SystemExit(0)

with open(f"/tmp/summary_{ticker}.json") as f:
    d = json.load(f)

news_str = "; ".join(d.get("news", [])[:3])
sr_line = ""
if d.get("support_20d"):
    sr_line = f"Support (20d): ${d['support_20d']}  Resistance (20d): ${d.get('resistance_20d', 'N/A')}  Pivot: ${d.get('pivot', 'N/A')}  R1: ${d.get('piv_r1', 'N/A')}  S1: ${d.get('piv_s1', 'N/A')}"
ctx_line = ""
if d.get("sp500_day_chg") is not None:
    ctx_line = f"S&P 500 today: {d['sp500_day_chg']:+.2f}%  Sector ETF ({d.get('sector_etf', 'N/A')}): {d.get('sector_day_chg', 0):+.2f}%  Relative strength vs sector: {d.get('relative_strength_1d', 0):+.2f}%"

# Long-term trend context — a stock badly lagging the market over both 1yr and 5yr is a
# structural-decline signal, not just a dip; Gemini is told to weigh this, not gate on it.
longterm_line = (
    f"1yr return: {d.get('stock_52w_change', 'N/A')}% (S&P {d.get('sp500_52w_change', 'N/A')}%)  "
    f"5yr return: {d.get('stock_5y_change', 'N/A')}% (S&P {d.get('sp500_5y_change', 'N/A')}%) "
    f"— if both badly lag the market, weigh that as a possible structural decline, not just a dip."
)
# Fundamentals — weak/negative values plus high debt and negative FCF mean the business may
# not survive a downturn; weigh this against any "it's cheap" narrative. Null = unknown, not zero.
fundamentals_line = (
    f"P/E: {d.get('pe_trailing') or 'N/A'} (fwd {d.get('pe_forward') or 'N/A'})  "
    f"Rev growth: {d.get('revenue_growth') or 'N/A'}  Earnings growth: {d.get('earnings_growth') or 'N/A'}  "
    f"Profit margin: {d.get('profit_margin') or 'N/A'}  ROE: {d.get('return_on_equity') or 'N/A'}  "
    f"D/E: {d.get('debt_to_equity') or 'N/A'}  FCF: {d.get('free_cashflow') or 'N/A'}  "
    f"Short float: {d.get('short_float_pct') or 'N/A'}  Inst. ownership: {d.get('inst_ownership_pct') or 'N/A'} "
    f"— weigh weak/negative fundamentals against any technical bounce; null means unknown, not zero."
)

prompt = f"""You are an independent stock analyst. Analyze {ticker} and return ONLY valid JSON with no markdown fences.

Data for {ticker}:
Price: ${d.get('price', 0):.2f} ({d.get('change_pct', 0):+.2f}% today)
52-week range: ${d.get('lo52', 0):.2f}-${d.get('hi52', 0):.2f} ({d.get('range_pct', 50):.1f}% of range)
RSI(14): {d.get('rsi', 50):.1f}
MA50: {d.get('ma50') or 'N/A'}  MA200: {d.get('ma200') or 'N/A'}
{sr_line}
{ctx_line}
{longterm_line}
{fundamentals_line}
Analyst consensus: {d.get('analyst', 'HOLD')}  Analyst upside: {d.get('upside_pct') or 'N/A'}%
Recent news: {news_str}
Next earnings: {d.get('earnings_date') or 'Unknown'}

Reply with exactly this JSON object and nothing else:
{{
  "verdict": "BUY or HOLD or SELL or WATCH",
  "reasoning": "5-8 sentence analysis",
  "conviction_score": 0,
  "risk_level": "LOW or MED or HIGH",
  "bull_case": "one sentence",
  "bear_case": "one sentence"
}}"""

client = genai.Client(api_key=api_key)
verdict_b = None

for attempt in range(3):
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            ),
        )
        raw = resp.text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        verdict_b = json.loads(raw)
        usage = getattr(resp, "usage_metadata", None)
        if usage:
            verdict_b["gemini_tokens_input"] = usage.prompt_token_count
            verdict_b["gemini_tokens_output"] = usage.candidates_token_count
        print(f"[{ticker}] Verdict B (Gemini): {verdict_b.get('verdict')}")
        break
    except Exception as e:
        print(f"[{ticker}] Gemini attempt {attempt + 1}/3 failed: {e}")
        if attempt < 2:
            time.sleep(30)

if verdict_b is None:
    print(f"[{ticker}] Gemini failed after 3 attempts — verdict_b will be null")
    verdict_b = {"verdict": None}

with open(f"/tmp/verdict_b_{ticker}.json", "w") as f:
    json.dump(verdict_b, f)
