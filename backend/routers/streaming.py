"""
Streaming router — SSE chatbot with web search tool.
Claude can call web_search when the existing analysis context isn't enough.
Tool use loop: stream → detect tool_use → execute search → continue stream.
"""
import asyncio
import json
import os
from datetime import datetime

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models import Conversation, Message, User
from routers.auth import get_current_user
from schemas import SendMessageRequest
from services.model_router import _estimate_max_tokens, _select_model
from services.prompt_builder import build_system_prompt

router = APIRouter(prefix="/conversations", tags=["streaming"])

_WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the web for current financial news, stock data, or any information "
        "not available in the existing analysis context. Use when the user asks about "
        "something that happened today or needs information beyond what's in tonight's analysis."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"}
        },
        "required": ["query"],
    },
}


async def _execute_web_search(query: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_ddg_search, query)


def _sync_ddg_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return "No search results found."
        parts = []
        for r in results:
            parts.append(f"**{r.get('title', '')}**\n{r.get('body', '')}\nSource: {r.get('href', '')}")
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        return f"Search failed: {e}"


async def _generate_title(content: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return content[:40]
    client = anthropic.AsyncAnthropic(api_key=api_key)
    resp = await client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=20,
        messages=[{"role": "user", "content": f"Give a 4-6 word title for this finance question: {content[:200]}"}],
    )
    return resp.content[0].text.strip().strip('"')


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: str,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
):
    user = get_current_user(body.id_token, db)
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.user_email != user.email:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    # Free-tier token cap disabled until there's an admin page to manage tiers/limits —
    # tokens_used is still tracked below for when that lands.

    # Load history
    history_rows = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).all()
    is_first = len(history_rows) == 0

    history = [{"role": m.role, "content": m.content} for m in history_rows]
    history.append({"role": "user", "content": body.content})

    # Save user message
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=body.content,
    )
    db.add(user_msg)
    db.commit()

    base_prompt, dynamic_context = build_system_prompt(user.email, db, conv.ticker)
    api_system = [{"type": "text", "text": base_prompt, "cache_control": {"type": "ephemeral"}}]
    if dynamic_context:
        api_system.append({"type": "text", "text": dynamic_context})

    max_tokens = _estimate_max_tokens(body.content)
    model = _select_model(body.content, max_tokens)

    title_task = asyncio.create_task(_generate_title(body.content)) if is_first else None

    async def generate():
        session = SessionLocal()
        full_text = ""
        total_in = total_out = total_cr = total_cw = 0
        persisted = False

        def persist():
            # Saves whatever was generated so far. Called both on the happy path and
            # from `finally`, so a client disconnect / dropped connection mid-stream
            # doesn't silently lose an assistant reply that Claude already generated
            # (and that already cost tokens).
            nonlocal persisted
            if persisted or not full_text:
                return
            persisted = True
            try:
                session.add(Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_text,
                    model_used=model,
                    input_tokens=total_in,
                    output_tokens=total_out,
                    cache_read_tokens=total_cr,
                    cache_write_tokens=total_cw,
                ))
                db_user = session.get(User, user.email)
                if db_user and db_user.tier != "premium" and not db_user.is_admin:
                    db_user.tokens_used = (db_user.tokens_used or 0) + total_in + total_out
                session.commit()
            except Exception:
                session.rollback()

        try:
            # Debug visibility into the actual system prompt sent to Claude — restricted
            # to a single account, not a general feature.
            if user.email == "ankur07jain@gmail.com":
                full_system_text = "\n\n".join(block["text"] for block in api_system)
                yield f"data: {json.dumps({'type': 'system_prompt', 'text': full_system_text})}\n\n"

            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                yield f"data: {json.dumps({'type': 'error', 'message': 'ANTHROPIC_API_KEY not configured'})}\n\n"
                return

            client = anthropic.AsyncAnthropic(api_key=api_key)
            messages = list(history)

            while True:
                current_tool_id = current_tool_name = current_tool_input = ""
                tool_uses: list[dict] = []

                async with client.messages.stream(
                    model=model,
                    max_tokens=max_tokens,
                    system=api_system,
                    messages=messages,
                    tools=[_WEB_SEARCH_TOOL],
                ) as stream:
                    async for event in stream:
                        etype = getattr(event, "type", "")

                        if etype == "content_block_start":
                            cb = getattr(event, "content_block", None)
                            if cb and getattr(cb, "type", "") == "tool_use":
                                current_tool_id = cb.id
                                current_tool_name = cb.name
                                current_tool_input = ""
                                yield f"data: {json.dumps({'type': 'tool_start', 'tool': current_tool_name})}\n\n"

                        elif etype == "content_block_delta":
                            delta = getattr(event, "delta", None)
                            if delta:
                                dtype = getattr(delta, "type", "")
                                if dtype == "text_delta":
                                    chunk = delta.text
                                    full_text += chunk
                                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                                elif dtype == "input_json_delta":
                                    current_tool_input += getattr(delta, "partial_json", "")

                        elif etype == "content_block_stop":
                            if current_tool_name:
                                try:
                                    parsed_input = json.loads(current_tool_input) if current_tool_input else {}
                                except Exception:
                                    parsed_input = {}
                                tool_uses.append({
                                    "id": current_tool_id,
                                    "name": current_tool_name,
                                    "input": parsed_input,
                                })
                                current_tool_name = ""

                    final = await stream.get_final_message()
                    usage = final.usage
                    total_in += usage.input_tokens
                    total_out += usage.output_tokens
                    total_cr += getattr(usage, "cache_read_input_tokens", 0) or 0
                    total_cw += getattr(usage, "cache_creation_input_tokens", 0) or 0

                if final.stop_reason == "end_turn" or not tool_uses:
                    break

                # Execute tool calls
                tool_results = []
                for tu in tool_uses:
                    if tu["name"] == "web_search":
                        query = tu["input"].get("query", "")
                        result = await _execute_web_search(query)
                        yield f"data: {json.dumps({'type': 'tool_result', 'query': query})}\n\n"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": result,
                        })

                messages.append({"role": "assistant", "content": final.content})
                messages.append({"role": "user", "content": tool_results})

            # Title
            nonlocal title_task
            if title_task:
                try:
                    new_title = await title_task
                    conv_db = session.get(Conversation, conversation_id)
                    if conv_db:
                        conv_db.title = new_title
                        conv_db.updated_at = datetime.utcnow()
                        session.commit()
                    yield f"data: {json.dumps({'type': 'title', 'title': new_title})}\n\n"
                except Exception:
                    pass

            persist()
            yield f"data: {json.dumps({'type': 'done', 'input_tokens': total_in, 'output_tokens': total_out})}\n\n"

        except Exception as e:
            persist()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            persist()
            session.close()

    return StreamingResponse(generate(), media_type="text/event-stream")
