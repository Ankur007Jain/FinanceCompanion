"""
Ripple Agent — uses Claude Sonnet to trace 2nd/3rd order effects of today's
macro news on the tracked ticker. Requires deep reasoning — uses Sonnet, not Haiku.
"""
import os
import anthropic

_SONNET = "claude-sonnet-4-6"

_SYSTEM = """You are explaining to a busy professional — not a finance expert — how today's broader news
might indirectly affect a specific stock they own or are watching.

Rules:
- Plain English only. No jargon. If you must use a term (e.g. "interest rates"), explain it in one phrase.
- Explain the cause-and-effect chain simply: "X happened → that means Y for this company → so the stock could Z"
- Only include effects that are realistic and have a clear logical connection. Skip vague "could impact" statements.
- If nothing in today's news meaningfully connects to this stock, say so in one sentence.
- Keep output to 3-5 sentences maximum.
"""


async def analyze_ripple(ticker: str, news_summary: str, sector: str = "") -> tuple[str, dict]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    _empty_usage = {"input_tokens": 0, "output_tokens": 0, "cache_read": 0, "cache_write": 0, "model": _SONNET}
    if not api_key or not news_summary or news_summary == "No recent news found.":
        return "No macro events with meaningful ripple effects identified today.", _empty_usage

    client = anthropic.AsyncAnthropic(api_key=api_key)
    prompt = (
        f"Ticker: {ticker}" + (f" (Sector: {sector})" if sector else "") + "\n\n"
        f"Today's news summary:\n{news_summary}\n\n"
        "Identify any 2nd or 3rd order ripple effects from today's macro or sector news "
        f"that could impact {ticker}. If none, say so."
    )
    resp = await client.messages.create(
        model=_SONNET, max_tokens=300,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
        "cache_write": getattr(resp.usage, "cache_write_input_tokens", 0) or 0,
        "model": _SONNET,
    }
    return resp.content[0].text.strip(), usage
