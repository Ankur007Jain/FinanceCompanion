"""
News Agent — fetches headlines from yfinance and Finnhub, deduplicates,
then uses Claude Haiku to produce a concise sentiment summary.
"""
import os
import asyncio
from typing import Optional

import finnhub
import yfinance as yf
import anthropic

_HAIKU = "claude-haiku-4-5-20251001"


def _finnhub_client() -> Optional[finnhub.Client]:
    key = os.getenv("FINNHUB_API_KEY", "")
    return finnhub.Client(api_key=key) if key else None


def _yf_news(ticker: str, yf_data=None) -> list[str]:
    try:
        items = (yf_data.news if yf_data is not None else yf.Ticker(ticker).news) or []
        lines = []
        for n in items[:8]:
            title = n.get("title", "")
            publisher = n.get("publisher", "")
            url = n.get("link") or n.get("url") or ""
            if url:
                lines.append(f"{title} [{publisher}] — {url}")
            else:
                lines.append(f"{title} [{publisher}]")
        return lines
    except Exception:
        return []


def _finnhub_news(ticker: str) -> list[str]:
    client = _finnhub_client()
    if not client:
        return []
    try:
        from datetime import date, timedelta
        today = date.today().isoformat()
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        items = client.company_news(ticker, _from=week_ago, to=today) or []
        lines = []
        for n in items[:8]:
            headline = n.get("headline", "")
            source = n.get("source", "")
            url = n.get("url") or ""
            if url:
                lines.append(f"{headline} [{source}] — {url}")
            else:
                lines.append(f"{headline} [{source}]")
        return lines
    except Exception:
        return []


def _deduplicate(yf_lines: list[str], fh_lines: list[str]) -> str:
    seen: set[str] = set()
    merged = []
    for line in yf_lines + fh_lines:
        key = line[:60].lower()
        if key not in seen:
            seen.add(key)
            merged.append(line)
    return "\n".join(merged[:12])


async def fetch_news(ticker: str, company_name: str = "", yf_data=None) -> str:
    loop = asyncio.get_event_loop()
    yf_lines, fh_lines = await asyncio.gather(
        loop.run_in_executor(None, _yf_news, ticker, yf_data),
        loop.run_in_executor(None, _finnhub_news, ticker),
    )
    raw = _deduplicate(yf_lines, fh_lines)
    if not raw.strip():
        return "No recent news found."

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return raw

    client = anthropic.AsyncAnthropic(api_key=api_key)
    name = company_name or ticker
    prompt = (
        f"You are analyzing recent news for {name} ({ticker}).\n\n"
        f"Raw headlines (with source URLs where available):\n{raw}\n\n"
        "Write a 3-4 sentence summary for a busy professional who is not a finance expert. "
        "Plain English only — no jargon. "
        "For the single most important story, name the source and include its URL in parentheses at the end of that sentence. "
        "Cover: what actually happened, whether it's good or bad for the stock, and any upcoming event to watch."
    )
    resp = await client.messages.create(
        model=_HAIKU, max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()
