"""
Streaming router — SSE chatbot with web search tool.
web_search is Anthropic's native server-side tool (Claude executes the search itself
and the result comes back inline in the same stream) — not a client-side tool we
execute and round-trip ourselves, unlike get_stock_analysis below. Previously used
duckduckgo_search (free, unofficial scraping library); switched off it after real
production chat logs showed repeated "Search is rate-limited" failures serious enough
that users noticed stale/wrong answers (Bitcoin price, exec changes, earnings news).
Tool use loop: stream → detect get_stock_analysis tool_use → execute → continue stream.
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
from models import Conversation, Message, ToolCall, User
from routers.auth import get_current_user
from schemas import SendMessageRequest
from services.model_router import _SONNET, _estimate_max_tokens
from services.prompt_builder import build_system_prompt, build_ticker_dossier

router = APIRouter(prefix="/conversations", tags=["streaming"])

_WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5,
}

_GET_STOCK_ANALYSIS_TOOL = {
    "name": "get_stock_analysis",
    "description": (
        "Get the full analysis for a ticker — verdict, conviction, bull/bear case, reasoning, "
        "news, ripple effects, memory of past lessons, and 5-day history. Use this when the user "
        "asks specifically about a ticker other than the one in focus (you only have a compact "
        "numeric summary for those). Works for any ticker, not just ones the user tracks. Prefer "
        "this over web_search for anything we've already analyzed — it's our own vetted data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "The stock ticker symbol, e.g. NVDA"}
        },
        "required": ["ticker"],
    },
}


def _log_web_searches(final, conversation_id: str, session) -> None:
    """Pairs each server_tool_use(web_search) block with its following
    web_search_tool_result block (Anthropic emits them adjacent, in order) and logs
    one ToolCall row per search — the only way to know actual search frequency and
    failure rate; the SSE events streamed to the client aren't persisted anywhere."""
    pending_query = None
    for block in getattr(final, "content", []) or []:
        btype = getattr(block, "type", "")
        if btype == "server_tool_use" and getattr(block, "name", "") == "web_search":
            pending_query = (getattr(block, "input", {}) or {}).get("query", "")
        elif btype == "web_search_tool_result" and pending_query is not None:
            content = getattr(block, "content", None)
            is_error = isinstance(content, dict) and content.get("type") == "web_search_tool_result_error"
            session.add(ToolCall(
                conversation_id=conversation_id, tool_name="web_search",
                query=pending_query, succeeded=not is_error,
            ))
            pending_query = None
    if pending_query is not None:
        # A server_tool_use with no matching result block shouldn't normally happen,
        # but don't silently drop the log entry if the API ever returns one.
        session.add(ToolCall(conversation_id=conversation_id, tool_name="web_search", query=pending_query, succeeded=False))
    session.commit()


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
        # Also cacheable: rebuilt fresh from the DB every call, so this only ever changes
        # when the underlying data actually changes (new nightly run, watchlist edit) — never
        # a staleness risk. Was silently never caching before (cache_read_tokens = 0 on every
        # production message): the static block alone is ~500 tokens, under Anthropic's
        # ~1024-token minimum to cache on Sonnet. This block easily clears it (~28k tokens
        # observed), so a 2nd+ message in the same conversation now hits it at ~10% cost
        # instead of paying full price for identical content again.
        api_system.append({"type": "text", "text": dynamic_context, "cache_control": {"type": "ephemeral"}})

    max_tokens = _estimate_max_tokens(body.content)
    # Always Sonnet — a router that downgraded short messages to Haiku was letting real
    # financial advice ("mrk" -> "MRK: Hold, don't sell today.") through the cheaper model,
    # because it judged model choice from the current message alone with no notion that
    # "no" or "1 more" is a continuation of an active buy/sell decision. Confirmed in
    # production logs before removing it. Quality is non-negotiable; Haiku stays reserved
    # for title generation and the overnight simple-field rewrites, neither of which is
    # advice a user acts on with money.
    model = _SONNET

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
                current_tool_id = current_tool_name = current_tool_input = current_tool_type = ""
                tool_uses: list[dict] = []

                async with client.messages.stream(
                    model=model,
                    max_tokens=max_tokens,
                    system=api_system,
                    messages=messages,
                    tools=[_WEB_SEARCH_TOOL, _GET_STOCK_ANALYSIS_TOOL],
                ) as stream:
                    async for event in stream:
                        etype = getattr(event, "type", "")

                        if etype == "content_block_start":
                            cb = getattr(event, "content_block", None)
                            cb_type = getattr(cb, "type", "") if cb else ""
                            # tool_use = client-side (get_stock_analysis), we execute and
                            # round-trip below. server_tool_use = web_search, Anthropic
                            # already executed it server-side by the time this stream
                            # finishes — nothing for us to run, just stream the UI event.
                            if cb_type in ("tool_use", "server_tool_use"):
                                current_tool_id = cb.id
                                current_tool_name = cb.name
                                current_tool_input = ""
                                current_tool_type = cb_type
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
                            if current_tool_name and current_tool_type == "tool_use":
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
                            current_tool_type = ""

                    final = await stream.get_final_message()
                    usage = final.usage
                    total_in += usage.input_tokens
                    total_out += usage.output_tokens
                    total_cr += getattr(usage, "cache_read_input_tokens", 0) or 0
                    total_cw += getattr(usage, "cache_creation_input_tokens", 0) or 0

                _log_web_searches(final, conversation_id, session)

                if final.stop_reason == "end_turn" or not tool_uses:
                    break

                # Execute client-side tool calls — get_stock_analysis only. web_search
                # is server-side and already resolved above; its result is already part
                # of `final.content`, which gets appended to `messages` unchanged below.
                tool_results = []
                for tu in tool_uses:
                    if tu["name"] == "get_stock_analysis":
                        pivot_ticker = tu["input"].get("ticker", "")
                        result = build_ticker_dossier(pivot_ticker, session, user.email)
                        session.add(ToolCall(
                            conversation_id=conversation_id, tool_name="get_stock_analysis",
                            query=pivot_ticker, succeeded=True,
                        ))
                        session.commit()
                        yield f"data: {json.dumps({'type': 'tool_result', 'query': pivot_ticker})}\n\n"
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
