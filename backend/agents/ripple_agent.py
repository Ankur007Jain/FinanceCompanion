"""
Ripple Agent — uses Claude Sonnet to trace 2nd/3rd order effects of today's
macro news on the tracked ticker. Requires deep reasoning — uses Sonnet, not Haiku.
"""
import os
import anthropic

_SONNET = "claude-sonnet-4-6"

_SYSTEM = """You are a senior financial analyst specializing in cross-sector impact analysis.
Your job is to identify second and third-order effects of macro events on specific stocks.

Rules:
- Be specific and mechanistic — explain the causal chain, not just "this could affect X"
- Distinguish between direct effects (1st order) and downstream effects (2nd/3rd order)
- Account for real-world physics and economics — do not trace effects that don't make logical sense
- If today's news has no meaningful ripple effect on this stock, say so clearly
- Keep output to 3-5 sentences maximum
"""


async def analyze_ripple(ticker: str, news_summary: str, sector: str = "") -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or not news_summary or news_summary == "No recent news found.":
        return "No macro events with meaningful ripple effects identified today."

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
    return resp.content[0].text.strip()
