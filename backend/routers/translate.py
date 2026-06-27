import json
import os
import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from routers.auth import get_current_user

router = APIRouter(prefix="/translate", tags=["translate"])

HAIKU = "claude-haiku-4-5-20251001"


class TranslateRequest(BaseModel):
    ticker: str
    language: str        # "en" | "hi"
    mode: str            # "technical" | "simple"
    fields: dict[str, Optional[str]]


class TranslateResponse(BaseModel):
    fields: dict[str, Optional[str]]


def _build_prompt(language: str, mode: str, fields: dict) -> str:
    lang_label = "Hindi" if language == "hi" else "English"
    mode_label = (
        "Use plain, everyday language. Avoid financial jargon — explain what each term means "
        "in simple words a non-investor would understand."
        if mode == "simple"
        else "Keep all financial and technical terms as-is."
    )

    entries = "\n".join(
        f'  "{k}": {json.dumps(v, ensure_ascii=False)}'
        for k, v in fields.items()
        if v
    )

    return f"""You are a financial content translator and simplifier.

Target language: {lang_label}
Style: {mode_label}

Translate and/or rewrite each field below into {lang_label}.
Return ONLY a valid JSON object with the exact same keys.
Preserve paragraph breaks. Do not add explanations outside the JSON.
If a field value is null, return null for that key.

Input fields:
{{
{entries}
}}"""


@router.post("", response_model=TranslateResponse)
def translate_analysis(
    body: TranslateRequest,
    id_token: str,
    db: Session = Depends(get_db),
):
    get_current_user(id_token, db)

    if body.language == "en" and body.mode == "technical":
        return TranslateResponse(fields=body.fields)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI service not configured.")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(body.language, body.mode, body.fields)

    try:
        msg = client.messages.create(
            model=HAIKU,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        translated = json.loads(raw)
    except (json.JSONDecodeError, IndexError, anthropic.APIError) as e:
        raise HTTPException(status_code=502, detail=f"Translation failed: {e}")

    # merge: keep original for any keys Haiku didn't return
    merged = {k: translated.get(k, v) for k, v in body.fields.items()}
    return TranslateResponse(fields=merged)
