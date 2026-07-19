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


def append_lesson(ticker: str, lesson: str, source: str, db: Session) -> "StockMemory":
    """Appends a tagged lesson to a ticker's shared memory — same write path for both
    the weekly Scorecard's systematic-failure feedback and chat's flag_stock_correction
    tool, so a correction caught in conversation reaches the nightly Verdict Agent the
    same way an audit-agent-caught one does. Global, not per-user: this is for facts
    about the TICKER, never personal context (that's user_learnings instead)."""
    from datetime import datetime
    ticker = ticker.upper()
    mem = db.get(StockMemory, ticker)
    tagged = f"[{source}] {lesson}"
    if mem:
        mem.memory_narrative = (f"{mem.memory_narrative}\n\n{tagged}")[:_MAX_CHARS]
        mem.last_updated = datetime.utcnow()
        mem.update_count = (mem.update_count or 0) + 1
    else:
        mem = StockMemory(ticker=ticker, memory_narrative=tagged, last_updated=datetime.utcnow(), update_count=1)
        db.add(mem)
    db.commit()
    return mem


async def update_memory_from_report(ticker: str, report_content: str, db: Session) -> None:
    """Extract lessons from a generated report and append to StockMemory."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return

    existing = await get_stock_memory(ticker, db)
    prompt = (
        f"Ticker: {ticker}\n\n"
        f"An AI report was just generated for this stock. Extract ONLY concrete lessons about what the AI "
        f"got wrong — bad entry targets, incorrect direction calls, data quality issues, patterns that didn't hold.\n\n"
        f"Report:\n{report_content}\n\n"
        f"Existing memory:\n{existing or '(none)'}\n\n"
        "Return a single updated memory paragraph (max 1200 chars) that keeps the existing context AND appends "
        "a short 'Past mistakes to avoid:' section with 2-3 specific bullet points. "
        "Every number or date you cite must come from the report or existing memory above — never invent "
        "one to sound precise. "
        "If the report shows no clear mistakes, reply exactly: NO_UPDATE"
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            model=_HAIKU, max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        result = resp.content[0].text.strip()
        if result.startswith("NO_UPDATE") or result == existing:
            return

        result = result[:_MAX_CHARS]
        from datetime import datetime
        mem = db.get(StockMemory, ticker)
        if mem:
            mem.memory_narrative = result
            mem.last_updated = datetime.utcnow()
            mem.update_count = (mem.update_count or 0) + 1
        else:
            db.add(StockMemory(ticker=ticker, memory_narrative=result, last_updated=datetime.utcnow(), update_count=1))
        db.commit()
    except Exception:
        pass


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
        "Every number or date must come from what's given above — never invent one. "
        "Do not include dates or bullet points — write as flowing prose."
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            model=_HAIKU, max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        result = resp.content[0].text.strip()
        # startswith, not ==: the model sometimes writes "NO_UPDATE" and then keeps going,
        # which used to leak the refusal text into stored memory (44/52 rows in production).
        if result.startswith("NO_UPDATE") or result == existing:
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
