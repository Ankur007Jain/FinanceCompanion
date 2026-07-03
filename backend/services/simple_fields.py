"""
Generate plain-English (simple) versions of the 5 key analysis text fields using Haiku.
Called after each nightly analysis is saved — fire-and-forget.
"""
import os
import logging
import anthropic
from sqlalchemy.orm import Session
from models import StockAnalysis

logger = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You rewrite financial analysis text into plain, jargon-free English for a general audience. "
    "Keep the same meaning and numbers. No bullet points — prose only. Same length or shorter."
)

_FIELDS = ["reasoning", "bull_case", "bear_case", "thesis_invalidation", "news_summary"]


async def generate_simple_fields(analysis: StockAnalysis, db: Session) -> None:
    """Rewrite text fields into plain English and save back to the analysis row."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return

    inputs = {f: getattr(analysis, f) for f in _FIELDS if getattr(analysis, f)}
    if not inputs:
        return

    prompt_parts = [f"{k}: {v}" for k, v in inputs.items()]
    prompt = (
        f"Ticker: {analysis.ticker}\n\n"
        "Rewrite each of the following fields in plain English. "
        "Return ONLY a JSON object with the same keys.\n\n"
        + "\n\n".join(prompt_parts)
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            model=_HAIKU,
            max_tokens=600,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        import json, re
        raw = resp.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        fields = json.loads(raw)

        for f in _FIELDS:
            if f in fields and fields[f]:
                setattr(analysis, f"{f}_simple", fields[f])
        db.commit()
        logger.info(f"[{analysis.ticker}] Simple fields saved.")
    except Exception as e:
        logger.warning(f"[{analysis.ticker}] Simple fields failed: {e}")
