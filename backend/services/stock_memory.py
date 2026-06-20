"""
Stock Memory — per-ticker prose narrative that persists across nightly runs.
Haiku decides whether tonight's analysis contains anything worth adding to the
running memory. Only updates when something genuinely new or significant happened.
"""
import os
from typing import Optional

import anthropic
from sqlalchemy.orm import Session

from models import StockMemory

_HAIKU = "claude-haiku-4-5-20251001"
_MAX_CHARS = 1200


async def get_stock_memory(ticker: str, db: Session) -> str:
    mem = db.get(StockMemory, ticker)
    return mem.memory_narrative if mem and mem.memory_narrative else ""


async def maybe_update_stock_memory(
    ticker: str,
    verdict: str,
    reasoning: str,
    news_summary: str,
    events_json: str,
    db: Session,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return

    existing = await get_stock_memory(ticker, db)
    prompt = (
        f"Ticker: {ticker}\n"
        f"Existing memory:\n{existing or '(none yet)'}\n\n"
        f"Tonight's verdict: {verdict}\n"
        f"Reasoning: {reasoning}\n"
        f"News: {news_summary}\n"
        f"Events: {events_json}\n\n"
        "Task: Update the memory with anything SIGNIFICANT and NEW — a major catalyst, "
        "a trend change, an upcoming event that matters, or a verdict reversal. "
        "If nothing important is new, reply with exactly: NO_UPDATE\n"
        "If updating, return the FULL updated memory as a single paragraph (max 1200 chars). "
        "Do not include dates or bullet points — write as flowing prose."
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            model=_HAIKU, max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        result = resp.content[0].text.strip()
        if result == "NO_UPDATE" or result == existing:
            return

        result = result[:_MAX_CHARS]
        mem = db.get(StockMemory, ticker)
        if mem:
            mem.memory_narrative = result
            from datetime import datetime
            mem.last_updated = datetime.utcnow()
            mem.update_count = (mem.update_count or 0) + 1
        else:
            from datetime import datetime
            db.add(StockMemory(
                ticker=ticker,
                memory_narrative=result,
                last_updated=datetime.utcnow(),
                update_count=1,
            ))
        db.commit()
    except Exception:
        pass
