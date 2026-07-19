"""
Tests for the Ask AI streaming endpoint's cost/quality changes:
- always Sonnet (no Haiku downgrade for short financial follow-ups)
- both system-prompt blocks marked cacheable
- get_stock_analysis tool present and dispatched correctly
"""
import os
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from services.model_router import _SONNET


def _mock_google_token(email: str = "streamtest@example.com"):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Stream Test"},
    )


def _server_web_search_block(query: str, failed: bool = False):
    """A pair of mock content blocks matching what Anthropic's native web_search tool
    (server_tool_use + web_search_tool_result) puts in final.content — _log_web_searches
    reads these directly, not the streamed SSE events, so tests can inject them straight
    into final_msg.content without simulating the full event sequence."""
    use_block = MagicMock()
    use_block.type = "server_tool_use"
    use_block.name = "web_search"
    use_block.input = {"query": query}

    result_block = MagicMock()
    result_block.type = "web_search_tool_result"
    result_block.content = {"type": "web_search_tool_result_error"} if failed else [{"title": "x", "url": "y"}]

    return [use_block, result_block]


@contextmanager
def _mock_anthropic_stream(text: str = "Test reply.", tool_use: dict | None = None, web_search_blocks: list | None = None):
    """tool_use, if given ({"name": ..., "input": {...}}), makes the mocked stream emit one
    tool_use block before ending (stop_reason=tool_use), so the second loop iteration can
    be asserted on too. Without it, a plain end_turn text reply.

    web_search_blocks, if given, is injected straight into final_msg.content — see
    _server_web_search_block(). Independent of `tool_use`, since a real turn can do a
    server-side web_search AND end_turn in the same response (no round-trip needed)."""
    events = []

    if tool_use:
        cb_start = MagicMock()
        cb_start.type = "content_block_start"
        # `name=` in the MagicMock() constructor sets the mock's repr, not a real .name
        # attribute — must assign it directly or current_tool_name never gets populated.
        content_block = MagicMock()
        content_block.type = "tool_use"
        content_block.id = "tu_1"
        content_block.name = tool_use["name"]
        cb_start.content_block = content_block
        events.append(cb_start)

        delta_event = MagicMock()
        delta_event.type = "content_block_delta"
        delta_event.delta = MagicMock(type="input_json_delta", partial_json=__import__("json").dumps(tool_use["input"]))
        events.append(delta_event)

        cb_stop = MagicMock()
        cb_stop.type = "content_block_stop"
        events.append(cb_stop)
    else:
        chunk = MagicMock()
        chunk.type = "content_block_delta"
        chunk.delta = MagicMock(type="text_delta", text=text)
        events.append(chunk)

    final_msg = MagicMock()
    final_msg.stop_reason = "tool_use" if tool_use else "end_turn"
    final_msg.usage = MagicMock(
        input_tokens=100, output_tokens=20,
        cache_read_input_tokens=0, cache_creation_input_tokens=0,
    )
    final_msg.content = list(web_search_blocks) if web_search_blocks else []

    stream_ctx = MagicMock()
    # Must be genuinely awaitable — a plain MagicMock() here makes `async with` raise
    # inside the generator, silently, since the exception surfaces after the response
    # has already started streaming (call_args are captured before the crash, which is
    # why simpler assertions on them can pass even when the body never actually renders).
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)

    # unittest.mock invokes an assigned dunder as a BOUND method (passing the mock
    # instance as the first arg) — a zero-arg async generator function raises
    # "takes 0 positional arguments but 1 was given" the moment `async for` runs.
    async def _aiter(_self):
        for e in events:
            yield e

    stream_ctx.__aiter__ = _aiter
    stream_ctx.get_final_message = AsyncMock(return_value=final_msg)

    mock_client = MagicMock()
    mock_client.messages.stream = MagicMock(return_value=stream_ctx)

    with patch("routers.streaming.anthropic.AsyncAnthropic", return_value=mock_client):
        yield mock_client


def _create_conversation(client: TestClient, ticker: str | None = None, email: str = "streamtest@example.com"):
    with _mock_google_token(email):
        r = client.post("/conversations", params={"id_token": "tok"}, json={"ticker": ticker})
    return r.json()["id"]


class TestAlwaysSonnet:
    def test_short_followup_message_still_uses_sonnet(self, client: TestClient):
        """Regression: 'mrk', 'no', '1 more' — short financial follow-ups — used to route
        to Haiku and got real hold/sell advice from the cheaper model. Confirmed in
        production logs. Now every chat reply must use Sonnet, full stop."""
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hold.") as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "no", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        assert mock_client.messages.stream.call_args.kwargs["model"] == _SONNET

    def test_greeting_also_uses_sonnet(self, client: TestClient):
        """Not just short-follow-ups — there is no Haiku path left in chat at all."""
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hey!") as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        assert mock_client.messages.stream.call_args.kwargs["model"] == _SONNET

    def test_analytical_question_uses_sonnet(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Analysis...") as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "should i sell or hold", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        assert mock_client.messages.stream.call_args.kwargs["model"] == _SONNET


class TestPromptCaching:
    def test_both_system_blocks_marked_cacheable(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hi.") as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        system = mock_client.messages.stream.call_args.kwargs["system"]
        # No learnings saved for this user -> the 3rd block is conditionally absent
        assert len(system) == 2
        assert system[0]["cache_control"] == {"type": "ephemeral"}
        assert system[1]["cache_control"] == {"type": "ephemeral"}

    def test_learnings_block_is_its_own_separately_cacheable_block(self, client: TestClient, db_session):
        """The whole reason this is split out: saving a new learning mid-conversation
        must only bust the cache for this small block, not the much larger
        dynamic_context block (ticker dossiers, correlations, watchlist) alongside it."""
        from models import UserLearning
        db_session.add(UserLearning(user_email="learncache@example.com", learning="Keeps answers short."))
        db_session.commit()

        conv_id = _create_conversation(client, email="learncache@example.com")
        with _mock_google_token("learncache@example.com"), _mock_anthropic_stream("Hi.") as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "learncache@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        system = mock_client.messages.stream.call_args.kwargs["system"]
        assert len(system) == 3
        assert all(block["cache_control"] == {"type": "ephemeral"} for block in system)
        assert "THINGS TO REMEMBER ABOUT THIS USER" in system[1]["text"]
        assert "Keeps answers short." in system[1]["text"]
        # And it's genuinely separate from the ticker/watchlist block, not just visually
        assert "THINGS TO REMEMBER" not in system[2]["text"]


class TestNativeWebSearch:
    """web_search switched from duckduckgo_search (unreliable, real production rate-limit
    failures) to Anthropic's native server-side tool. Server-side means Claude executes
    the search itself — no client-side round-trip, unlike get_stock_analysis."""

    def test_web_search_tool_uses_native_server_side_shape(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hi.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        tools = mock_client.messages.stream.call_args.kwargs["tools"]
        web_search = next(t for t in tools if t["name"] == "web_search")
        assert web_search["type"] == "web_search_20250305"
        assert "input_schema" not in web_search  # native tool, not a client-side one

    def test_successful_search_logged_as_tool_call(self, client: TestClient, db_session):
        from models import ToolCall
        conv_id = _create_conversation(client)
        blocks = _server_web_search_block("current NVDA news")
        with _mock_google_token(), _mock_anthropic_stream("Here's what I found.", web_search_blocks=blocks):
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "what's happening with NVDA today", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        calls = db_session.query(ToolCall).filter(ToolCall.conversation_id == conv_id).all()
        assert len(calls) == 1
        assert calls[0].tool_name == "web_search"
        assert calls[0].query == "current NVDA news"
        assert calls[0].succeeded is True

    def test_failed_search_logged_as_unsuccessful(self, client: TestClient, db_session):
        """This is the exact real-world failure this change targets: production logs
        showed "Search is rate-limited right now" — the search must be logged as failed,
        not silently dropped, so this kind of regression is diagnosable from data next time."""
        from models import ToolCall
        conv_id = _create_conversation(client)
        blocks = _server_web_search_block("bitcoin price today", failed=True)
        with _mock_google_token(), _mock_anthropic_stream("I couldn't get current data on that.", web_search_blocks=blocks):
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "bitcoin price?", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        call = db_session.query(ToolCall).filter(ToolCall.conversation_id == conv_id).first()
        assert call.succeeded is False

    def test_server_side_search_does_not_trigger_client_round_trip(self, client: TestClient):
        """A server-side web_search block must never land in the tool_uses list that
        drives the client-side execute-and-continue loop — it's already resolved by
        the time final.content is available. Asserting the endpoint completes cleanly
        with stop_reason=end_turn and a single .stream() call (no second round trip)."""
        conv_id = _create_conversation(client)
        blocks = _server_web_search_block("some query")
        with _mock_google_token(), _mock_anthropic_stream("Done.", web_search_blocks=blocks) as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "search something", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        assert mock_client.messages.stream.call_count == 1


class TestGetStockAnalysisTool:
    def test_tool_is_offered(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hi.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        tools = mock_client.messages.stream.call_args.kwargs["tools"]
        names = {t["name"] for t in tools}
        assert "get_stock_analysis" in names
        assert "web_search" in names

    def test_pivot_ticker_tool_call_dispatches_to_real_dossier_builder(self, client: TestClient, db_session):
        """When Claude calls get_stock_analysis(ZPIVOT), the dispatcher must call the same
        build_ticker_dossier() the focus ticker uses — not a stub — so a pivot mid-chat
        gets identical depth (dossier + history + memory) to the original focus ticker."""
        from datetime import date
        from models import StockAnalysis

        db_session.add(StockAnalysis(
            ticker="ZPIVOT", analysis_date=date.today(), verdict="BUY",
            conviction_score=80, bull_case="AI demand.", current_price=200.0,
        ))
        db_session.commit()

        conv_id = _create_conversation(client, ticker="TSLA")

        from services.prompt_builder import build_ticker_dossier as real_dossier_fn
        captured_results = []

        def _spy(*args, **kwargs):
            result = real_dossier_fn(*args, **kwargs)
            captured_results.append(result)
            return result

        # A second .stream() call inside the tool loop would need its own fully-shaped
        # mock; rather than chaining two fragile mock stream contexts, drive the endpoint
        # once with a tool_use response and directly assert the real dossier builder
        # (imported into streaming.py) gets invoked with the right ticker + user.
        with _mock_google_token(), \
             _mock_anthropic_stream("", tool_use={"name": "get_stock_analysis", "input": {"ticker": "ZPIVOT"}}) as mock_client, \
             patch("routers.streaming.build_ticker_dossier", side_effect=_spy) as spy:
            mock_client.messages.create = AsyncMock(return_value=MagicMock(content=[MagicMock(text="Title")]))
            # Second .stream() call (after the tool result) just needs to not blow up;
            # reuse the same tool_use response shape but treat it as end_turn on the retry.
            call_count = {"n": 0}
            base_return = mock_client.messages.stream.return_value

            def _side_effect(**kwargs):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return base_return
                base_return.get_final_message = AsyncMock(return_value=MagicMock(
                    stop_reason="end_turn", content=[],
                    usage=MagicMock(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0),
                ))
                return base_return
            mock_client.messages.stream.side_effect = _side_effect

            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "what about ZPIVOT?", "user_email": "streamtest@example.com", "id_token": "tok"},
            )

        assert r.status_code == 200
        spy.assert_called_once()
        assert spy.call_args.args[0].upper() == "ZPIVOT"
        assert spy.call_args.args[2] == "streamtest@example.com"
        # And the real function actually returned ZPIVOT's dossier (not a stub)
        assert len(captured_results) == 1
        assert "ZPIVOT — FULL ANALYSIS" in captured_results[0]
        assert "AI demand." in captured_results[0]


def _make_second_call_end_turn(mock_client):
    """Shared boilerplate for dispatch tests: the first .stream() call returns a
    tool_use (from _mock_anthropic_stream), the second — after the tool result is fed
    back — just needs to end the turn cleanly without blowing up the loop."""
    call_count = {"n": 0}
    base_return = mock_client.messages.stream.return_value

    def _side_effect(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return base_return
        base_return.get_final_message = AsyncMock(return_value=MagicMock(
            stop_reason="end_turn", content=[],
            usage=MagicMock(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0),
        ))
        return base_return
    mock_client.messages.stream.side_effect = _side_effect


class TestCappedHistory:
    def test_only_recent_messages_sent_live(self, client: TestClient, db_session):
        """Real production evidence: one 116-message conversation showed 68x cost growth
        and hit 60.8% of Sonnet's 200K context window on a single turn, because the
        entire history was resent uncapped every time. Only the most recent messages
        should go out live."""
        from models import Message
        conv_id = _create_conversation(client)
        for i in range(30):
            db_session.add(Message(conversation_id=conv_id, role="user", content=f"msg {i}"))
        db_session.commit()

        with _mock_google_token(), _mock_anthropic_stream("Reply.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "latest", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        sent_messages = mock_client.messages.stream.call_args.kwargs["messages"]
        # 20 capped history + 1 new user message
        assert len(sent_messages) == 21
        # And it's the MOST RECENT ones, not the oldest
        contents = [m["content"] for m in sent_messages]
        assert "msg 29" in contents
        assert "msg 0" not in contents

    def test_short_conversation_unaffected_by_cap(self, client: TestClient, db_session):
        from models import Message
        conv_id = _create_conversation(client)
        for i in range(5):
            db_session.add(Message(conversation_id=conv_id, role="user", content=f"msg {i}"))
        db_session.commit()

        with _mock_google_token(), _mock_anthropic_stream("Reply.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "latest", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        sent_messages = mock_client.messages.stream.call_args.kwargs["messages"]
        assert len(sent_messages) == 6  # all 5 + the new one, nothing trimmed


class TestGetChatHistoryTool:
    def test_tool_is_offered(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hi.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        names = {t["name"] for t in mock_client.messages.stream.call_args.kwargs["tools"]}
        assert "get_chat_history" in names

    def test_retrieves_verbatim_messages_from_other_ticker_conversation(self, client: TestClient, db_session):
        """The actual evidenced need: a user asked whether the AI could see messages
        from a differently-scoped conversation about the same ticker. It couldn't.
        This tool is the fix — real quoted messages, not a summary."""
        from models import Conversation, Message
        conv_id = _create_conversation(client, ticker="GLD")
        other_conv = Conversation(id="other-slv-conv", user_email="streamtest@example.com", ticker="SLV")
        db_session.add(other_conv)
        db_session.add(Message(conversation_id="other-slv-conv", role="user", content="Does SLV overlap with GLD?"))
        db_session.add(Message(conversation_id="other-slv-conv", role="assistant", content="Yes, 0.85 correlation."))
        db_session.commit()

        with _mock_google_token(), \
             _mock_anthropic_stream("", tool_use={"name": "get_chat_history", "input": {"ticker": "SLV"}}) as mock_client:
            _make_second_call_end_turn(mock_client)
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "what did we say about SLV?", "user_email": "streamtest@example.com", "id_token": "tok"},
            )

        assert r.status_code == 200
        # The tool result content is fed back as the 2nd-to-last message's content
        sent_messages = mock_client.messages.stream.call_args.kwargs["messages"]
        tool_result_content = sent_messages[-1]["content"][0]["content"]
        assert "Does SLV overlap with GLD?" in tool_result_content
        assert "0.85 correlation" in tool_result_content

    def test_no_ticker_pulls_trimmed_older_portion_of_same_conversation(self, client: TestClient, db_session):
        from models import Message
        conv_id = _create_conversation(client)
        for i in range(25):
            db_session.add(Message(conversation_id=conv_id, role="user", content=f"old message {i}"))
        db_session.commit()

        with _mock_google_token(), \
             _mock_anthropic_stream("", tool_use={"name": "get_chat_history", "input": {}}) as mock_client:
            _make_second_call_end_turn(mock_client)
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "what did I say earlier?", "user_email": "streamtest@example.com", "id_token": "tok"},
            )

        assert r.status_code == 200
        sent_messages = mock_client.messages.stream.call_args.kwargs["messages"]
        tool_result_content = sent_messages[-1]["content"][0]["content"]
        assert "old message 0" in tool_result_content  # trimmed off the live 20, but retrievable

    def test_no_match_returns_friendly_message_not_crash(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), \
             _mock_anthropic_stream("", tool_use={"name": "get_chat_history", "input": {"ticker": "ZNOPE"}}) as mock_client:
            _make_second_call_end_turn(mock_client)
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "what about ZNOPE?", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        sent_messages = mock_client.messages.stream.call_args.kwargs["messages"]
        tool_result_content = sent_messages[-1]["content"][0]["content"]
        assert "No other conversation found" in tool_result_content


class TestSaveLearningTool:
    def test_tool_is_offered(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hi.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        names = {t["name"] for t in mock_client.messages.stream.call_args.kwargs["tools"]}
        assert "save_learning" in names

    def test_saves_a_real_learning_row(self, client: TestClient, db_session):
        from models import UserLearning
        conv_id = _create_conversation(client)
        with _mock_google_token(), \
             _mock_anthropic_stream("", tool_use={"name": "save_learning", "input": {"learning": "Manages 48 stocks total."}}) as mock_client:
            _make_second_call_end_turn(mock_client)
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "remember I manage 48 stocks", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        row = db_session.query(UserLearning).filter(UserLearning.user_email == "streamtest@example.com").first()
        assert row is not None
        assert row.learning == "Manages 48 stocks total."
        assert row.source_conversation_id == conv_id

    def test_empty_learning_does_not_save(self, client: TestClient, db_session):
        # Shared on-disk SQLite test DB across the whole file — assert a delta, not an
        # absolute count, since an earlier test in this module may have already saved
        # a row for this same user_email.
        from models import UserLearning
        before = db_session.query(UserLearning).filter(UserLearning.user_email == "streamtest@example.com").count()
        conv_id = _create_conversation(client)
        with _mock_google_token(), \
             _mock_anthropic_stream("", tool_use={"name": "save_learning", "input": {"learning": ""}}) as mock_client:
            _make_second_call_end_turn(mock_client)
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        after = db_session.query(UserLearning).filter(UserLearning.user_email == "streamtest@example.com").count()
        assert after == before


class TestFlagStockCorrectionTool:
    def test_tool_is_offered(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hi.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        names = {t["name"] for t in mock_client.messages.stream.call_args.kwargs["tools"]}
        assert "flag_stock_correction" in names

    def test_correction_updates_shared_stock_memory(self, client: TestClient, db_session):
        """This is the piece that benefits every user, not just the one who caught the
        mistake — same write path (append_lesson) the weekly Scorecard uses, now also
        reachable from a live chat correction."""
        from models import StockMemory
        conv_id = _create_conversation(client, ticker="INTC")
        with _mock_google_token(), \
             _mock_anthropic_stream("", tool_use={
                 "name": "flag_stock_correction",
                 "input": {"ticker": "INTC", "correction": "Lip-Bu Tan is CEO, not Pat Gelsinger."},
             }) as mock_client:
            _make_second_call_end_turn(mock_client)
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "that's wrong, Gelsinger left", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        mem = db_session.get(StockMemory, "INTC")
        assert mem is not None
        assert "[Chat] Lip-Bu Tan is CEO, not Pat Gelsinger." in mem.memory_narrative

    def test_missing_fields_does_not_save(self, client: TestClient, db_session):
        # Empty ticker/correction would key a StockMemory row on ticker="" if the
        # guard didn't hold — check that specific row is absent rather than an
        # absolute table count (shared on-disk SQLite test DB across this module).
        from models import StockMemory
        conv_id = _create_conversation(client)
        with _mock_google_token(), \
             _mock_anthropic_stream("", tool_use={"name": "flag_stock_correction", "input": {"ticker": "", "correction": ""}}) as mock_client:
            _make_second_call_end_turn(mock_client)
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        assert db_session.get(StockMemory, "") is None
