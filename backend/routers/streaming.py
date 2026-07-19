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
from models import Conversation, Message, ToolCall, User, UserLearning
from routers.auth import get_current_user
from schemas import SendMessageRequest
from services.model_router import _SONNET, _estimate_max_tokens
from services.prompt_builder import build_system_prompt, build_ticker_dossier, build_user_learnings_block
from services.stock_memory import append_lesson

router = APIRouter(prefix="/conversations", tags=["streaming"])

# Only the most recent messages are resent live each turn — a real production
# conversation was found sending the ENTIRE history every turn with no cap: 68x cost
# growth within one conversation (1.8K -> 119K uncached input tokens), and by message
# 57 alone that's 60.8% of Sonnet's 200K context window — a live collision course with
# a hard failure, not just rising cost. get_chat_history is the safety valve for
# whatever this trims off (see below) — verbatim retrieval, not silent data loss.
_MAX_LIVE_HISTORY = 20

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

_GET_CHAT_HISTORY_TOOL = {
    "name": "get_chat_history",
    "description": (
        "Retrieve real past messages — either from the user's OTHER conversations about a "
        "specific ticker, or older messages from earlier in THIS conversation that are no "
        "longer in the live context (only the most recent ~20 messages are kept live for cost "
        "reasons). Always returns real quoted messages, never a summary. Use this when the user "
        "references something discussed before that you don't see in the current context — "
        "'like we discussed', 'in my SLV chat', or asking about a ticker they've talked about "
        "elsewhere."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Ticker to find past conversations about, e.g. SLV. Omit to look further back in this same conversation instead.",
            }
        },
        "required": [],
    },
}

_SAVE_LEARNING_TOOL = {
    "name": "save_learning",
    "description": (
        "Save a durable fact, preference, or instruction about this user that should be "
        "remembered in every future conversation. Two scopes: leave ticker empty for a "
        "GLOBAL fact ('manages 48 stocks', 'keep answers short'); set ticker for a personal "
        "note tied to one stock ('already knows SLV/GLD overlap, don't re-explain it'). This "
        "is always private to this user — for an objective correction about the ticker itself "
        "that should help every user, use flag_stock_correction instead.\n\n"
        "Trigger on explicit language ('remember...', 'from now on...', 'don't forget...') or "
        "a clearly stated lasting preference/fact — call this directly, no need to check first. "
        "If you're INFERRING something might be worth remembering from a pattern in the "
        "conversation rather than the user stating it outright, ask them to confirm before "
        "calling this tool — don't save an inferred guess as if it were a confirmed instruction. "
        "Do NOT use this for one-off statements or anything already visible in their "
        "watchlist/portfolio data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "learning": {"type": "string", "description": "The fact/preference/instruction, stated concisely in one sentence"},
            "ticker": {"type": "string", "description": "Leave empty for global. Set to a ticker for a personal note tied to that stock only."},
        },
        "required": ["learning"],
    },
}

_DELETE_LEARNING_TOOL = {
    "name": "delete_learning",
    "description": (
        "Remove a previously saved learning — use when the user says something was saved "
        "wrong, no longer applies, or asks you to forget something. Pass the learning's exact "
        "text as it appears in 'THINGS TO REMEMBER ABOUT THIS USER' or 'Things you've told me "
        "about this ticker specifically' in your context — copy it verbatim, don't paraphrase. "
        "If you're not sure which saved learning the user means, ask them to confirm which one "
        "before calling this — deleting the wrong one is worse than asking."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "learning": {"type": "string", "description": "The exact text of the learning to remove, copied verbatim from context"},
        },
        "required": ["learning"],
    },
}

_FLAG_CORRECTION_TOOL = {
    "name": "flag_stock_correction",
    "description": (
        "Flag a factual correction about a TICKER ITSELF — not the user's personal situation — "
        "that should be remembered for every future analysis of that stock and shared with "
        "every user tracking it, e.g. correcting an outdated fact you stated (a former "
        "executive, a stale price, superseded news). This updates the stock's shared memory "
        "that the nightly analysis reads every night. Do NOT use this for the user's personal "
        "preferences — use save_learning for those."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string"},
            "correction": {"type": "string", "description": "The correction, stated as one specific factual sentence"},
        },
        "required": ["ticker", "correction"],
    },
}


def _fetch_chat_history(ticker: str, conversation_id: str, user_email: str, db) -> str:
    """Verbatim retrieval, never summarized — the safety valve for the capped live
    window and the mechanism for cross-conversation memory, same tool either way.
    ticker given -> search the user's OTHER conversations for that ticker. No ticker
    -> pull the trimmed-off older portion of THIS conversation."""
    _RETRIEVE_LIMIT = 15
    if ticker:
        ticker = ticker.upper()
        other_conv = (
            db.query(Conversation)
            .filter(
                Conversation.user_email == user_email,
                Conversation.ticker == ticker,
                Conversation.id != conversation_id,
            )
            .order_by(Conversation.updated_at.desc())
            .first()
        )
        if not other_conv:
            return f"No other conversation found about {ticker}."
        rows = (
            db.query(Message)
            .filter(Message.conversation_id == other_conv.id)
            .order_by(Message.created_at.desc())
            .limit(_RETRIEVE_LIMIT)
            .all()
        )
        rows.reverse()
        if not rows:
            return f"No other conversation found about {ticker}."
        header = f"--- Real messages from your other {ticker} conversation ({other_conv.updated_at.date().isoformat()}) ---"
    else:
        all_rows = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .all()
        )
        older = all_rows[:-_MAX_LIVE_HISTORY] if len(all_rows) > _MAX_LIVE_HISTORY else []
        if not older:
            return "No earlier messages in this conversation beyond what's already in context."
        rows = older[-_RETRIEVE_LIMIT:]
        header = "--- Earlier messages from this conversation, no longer in live context ---"

    lines = [header] + [f"[{r.role}]: {r.content}" for r in rows]
    return "\n\n".join(lines)


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

    # Load history — capped to the most recent _MAX_LIVE_HISTORY messages. Anything
    # trimmed off is still fetchable verbatim via the get_chat_history tool, not lost.
    history_rows = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).all()
    is_first = len(history_rows) == 0
    live_rows = history_rows[-_MAX_LIVE_HISTORY:] if len(history_rows) > _MAX_LIVE_HISTORY else history_rows

    history = [{"role": m.role, "content": m.content} for m in live_rows]
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
    learnings_block = build_user_learnings_block(user.email, db)
    api_system = [{"type": "text", "text": base_prompt, "cache_control": {"type": "ephemeral"}}]
    if learnings_block:
        # Its OWN cache block, separate from dynamic_context below — a user can save a
        # new learning mid-conversation, and dynamic_context can be tens of thousands of
        # tokens (ticker dossiers, correlations, watchlist). Without this split, saving
        # one learning would bust the cache for that whole block on every following turn;
        # this way only the small learnings block needs a fresh cache_write. Note: like
        # any cache_control block, this only actually caches once it clears Anthropic's
        # ~1024-token minimum — a user with just a couple of short saved learnings won't
        # see a cache hit here, but the block is proportionally cheap either way at that
        # size; the win compounds for users who've saved many over time.
        api_system.append({"type": "text", "text": learnings_block, "cache_control": {"type": "ephemeral"}})
    if dynamic_context:
        # Also cacheable: rebuilt fresh from the DB every call, so this only ever changes
        # when the underlying data actually changes (new nightly run, watchlist edit) — never
        # a staleness risk. Was silently never caching before (cache_read_tokens = 0 on every
        # production message): the static block alone is ~500 tokens, under Anthropic's
        # ~1024-token minimum to cache on Sonnet. This block easily clears it (~28k tokens
        # observed), so a 2nd+ message in the same conversation now hits it at ~10% cost
        # instead of paying full price for identical content again. As of the split below,
        # this block no longer contains the focus ticker's dossier — it's the same content
        # regardless of which ticker is in focus, so it stays cache-shareable across every
        # ticker-scoped conversation this user has, not just repeated turns in one.
        api_system.append({"type": "text", "text": dynamic_context, "cache_control": {"type": "ephemeral"}})

    if conv.ticker:
        # The focus ticker's full dossier — deliberately the LAST block in the array,
        # not folded into dynamic_context above. Anthropic's cache breakpoints match
        # an exact PREFIX up to each cache_control marker, not each block in isolation:
        # if this (which changes every time the user switches which ticker they're
        # viewing) came before the shared block above, it would poison that block's
        # cache match too, even though its own content is otherwise identical across
        # every ticker-scoped conversation. Putting it last means only THIS block
        # needs a fresh write on a switch — confirmed with real data: it was the
        # cause of a 71%-of-block cache miss on every ticker switch before this split.
        focus_dossier = (
            f"📌 ACTIVE CONVERSATION TOPIC: {conv.ticker}. The user is chatting specifically about "
            f"{conv.ticker} right now. When they say \"this stock\", \"this share\", \"it\", or similar, "
            f"they mean {conv.ticker} — not any other ticker listed above. Lead your answer with "
            f"{conv.ticker}; only bring in other tickers if the user explicitly asks about them.\n\n"
        ) + build_ticker_dossier(conv.ticker, db, user.email)
        api_system.append({"type": "text", "text": focus_dossier, "cache_control": {"type": "ephemeral"}})

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
                    tools=[
                        _WEB_SEARCH_TOOL, _GET_STOCK_ANALYSIS_TOOL, _GET_CHAT_HISTORY_TOOL,
                        _SAVE_LEARNING_TOOL, _DELETE_LEARNING_TOOL, _FLAG_CORRECTION_TOOL,
                    ],
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

                # Execute client-side tool calls. web_search is server-side and already
                # resolved above; its result is already part of `final.content`, which
                # gets appended to `messages` unchanged below.
                tool_results = []
                for tu in tool_uses:
                    name = tu["name"]
                    if name == "get_stock_analysis":
                        pivot_ticker = tu["input"].get("ticker", "")
                        result = build_ticker_dossier(pivot_ticker, session, user.email)
                        session.add(ToolCall(
                            conversation_id=conversation_id, tool_name="get_stock_analysis",
                            query=pivot_ticker, succeeded=True,
                        ))
                        session.commit()
                        yield f"data: {json.dumps({'type': 'tool_result', 'query': pivot_ticker})}\n\n"
                        tool_results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": result})

                    elif name == "get_chat_history":
                        ticker = tu["input"].get("ticker", "")
                        result = _fetch_chat_history(ticker, conversation_id, user.email, session)
                        session.add(ToolCall(
                            conversation_id=conversation_id, tool_name="get_chat_history",
                            query=ticker or "(this conversation, older messages)", succeeded=True,
                        ))
                        session.commit()
                        yield f"data: {json.dumps({'type': 'tool_result', 'query': ticker or 'chat history'})}\n\n"
                        tool_results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": result})

                    elif name == "save_learning":
                        learning = tu["input"].get("learning", "").strip()
                        learn_ticker = (tu["input"].get("ticker") or "").strip().upper() or None
                        if learning:
                            session.add(UserLearning(
                                user_email=user.email, learning=learning, ticker=learn_ticker,
                                source_conversation_id=conversation_id,
                            ))
                        session.add(ToolCall(
                            conversation_id=conversation_id, tool_name="save_learning",
                            query=f"[{learn_ticker or 'global'}] {learning}", succeeded=bool(learning),
                        ))
                        session.commit()
                        yield f"data: {json.dumps({'type': 'tool_result', 'query': learning})}\n\n"
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": tu["id"],
                            "content": "Saved." if learning else "Nothing to save — learning was empty.",
                        })

                    elif name == "delete_learning":
                        target_text = tu["input"].get("learning", "").strip()
                        deleted = 0
                        if target_text:
                            deleted = (
                                session.query(UserLearning)
                                .filter(UserLearning.user_email == user.email, UserLearning.learning == target_text)
                                .delete()
                            )
                        session.add(ToolCall(
                            conversation_id=conversation_id, tool_name="delete_learning",
                            query=target_text, succeeded=bool(deleted),
                        ))
                        session.commit()
                        yield f"data: {json.dumps({'type': 'tool_result', 'query': target_text})}\n\n"
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": tu["id"],
                            "content": "Removed." if deleted else "No exact match found for that text — nothing removed.",
                        })

                    elif name == "flag_stock_correction":
                        ticker = tu["input"].get("ticker", "").strip()
                        correction = tu["input"].get("correction", "").strip()
                        if ticker and correction:
                            append_lesson(ticker, correction, "Chat", session)
                        session.add(ToolCall(
                            conversation_id=conversation_id, tool_name="flag_stock_correction",
                            query=f"{ticker}: {correction}", succeeded=bool(ticker and correction),
                        ))
                        session.commit()
                        yield f"data: {json.dumps({'type': 'tool_result', 'query': ticker})}\n\n"
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": tu["id"],
                            "content": "Saved to shared memory." if (ticker and correction) else "Missing ticker or correction — not saved.",
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
