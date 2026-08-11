"""
Tests for the Ask AI streaming endpoint's cost/quality changes:
- always Sonnet (no Haiku downgrade for short financial follow-ups)
- both system-prompt blocks marked cacheable
- get_stock_analysis tool present and dispatched correctly
"""
import json
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
def _mock_anthropic_stream(
    text: str = "Test reply.", tool_use: dict | None = None,
    web_search_blocks: list | None = None, thinking: bool = False,
):
    """tool_use, if given ({"name": ..., "input": {...}}), makes the mocked stream emit one
    tool_use block before ending (stop_reason=tool_use), so the second loop iteration can
    be asserted on too. Without it, a plain end_turn text reply.

    web_search_blocks, if given, is injected straight into final_msg.content — see
    _server_web_search_block(). Independent of `tool_use`, since a real turn can do a
    server-side web_search AND end_turn in the same response (no round-trip needed).

    thinking=True prepends a thinking content_block_start/delta/stop sequence before
    the text — matches a real extended-thinking response's shape, so tests can verify
    thinking content never leaks into full_text (only text_delta does)."""
    events = []

    if thinking:
        think_start = MagicMock()
        think_start.type = "content_block_start"
        think_block = MagicMock()
        think_block.type = "thinking"
        think_start.content_block = think_block
        events.append(think_start)

        think_delta = MagicMock()
        think_delta.type = "content_block_delta"
        think_delta.delta = MagicMock(type="thinking_delta", thinking="Reasoning through this...")
        events.append(think_delta)

        think_stop = MagicMock()
        think_stop.type = "content_block_stop"
        events.append(think_stop)

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


class TestExtendedThinking:
    def test_complex_decision_enables_thinking(self, client: TestClient):
        from services.model_router import _THINKING_EFFORT, _THINKING_MIN_MAX_TOKENS
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Let's rebalance.") as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "should I rebalance my portfolio", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        kwargs = mock_client.messages.stream.call_args.kwargs
        # Sonnet 5 requires adaptive thinking, not the old enabled+budget_tokens shape
        # (real production 400: "thinking.type.enabled is not supported for this model").
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert kwargs["output_config"] == {"effort": _THINKING_EFFORT}
        # max_tokens must have enough headroom for thinking + the final answer, not
        # just reuse whatever tier _estimate_max_tokens picked for a plain message.
        assert kwargs["max_tokens"] >= _THINKING_MIN_MAX_TOKENS

    def test_simple_question_does_not_enable_thinking(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hi.") as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        assert "thinking" not in mock_client.messages.stream.call_args.kwargs

    def test_thinking_start_event_streamed(self, client: TestClient):
        """The extra latency thinking adds shouldn't read as a silent hang — a
        thinking_start SSE event fires so a future UI can show progress."""
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Done thinking.", thinking=True) as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "should I rebalance", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        assert '"type": "thinking_start"' in r.text

    def test_thinking_content_never_leaks_into_saved_message(self, client: TestClient, db_session):
        """Only text_delta ever appends to full_text (the saved assistant message) —
        confirming a thinking block alongside real text doesn't contaminate it."""
        from models import Message
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("The real answer.", thinking=True):
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "should I rebalance", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        saved = db_session.query(Message).filter(Message.conversation_id == conv_id, Message.role == "assistant").first()
        assert saved.content == "The real answer."


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
        # 1h here too, even though this block never actually caches (it's under the
        # 1024-token minimum) — required so this block's TTL isn't "lower" than the
        # ones that follow it (system.1, system.2), which the real API rejects with
        # a 400. The mock client here doesn't enforce that, which is exactly how this
        # broke in production without a failing test catching it first.
        assert system[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        # dynamic_context: 1h TTL — it's the largest block and only changes with the
        # underlying data, so there's no reason to let it cold-write on a 5-min gap.
        assert system[1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}

    def test_learnings_are_merged_into_the_static_block(self, client: TestClient, db_session):
        """Learnings used to be their own breakpoint; merged into the static block to
        free a cache-breakpoint slot (Anthropic caps a request at 4 total) for caching
        the messages array itself. Still must not leak into dynamic_context, which
        stays cache-shareable across every ticker-scoped conversation this user has."""
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
        assert len(system) == 2
        # 1h here too, even though this block never actually caches (it's under the
        # 1024-token minimum) — required so this block's TTL isn't "lower" than the
        # ones that follow it (system.1, system.2), which the real API rejects with
        # a 400. The mock client here doesn't enforce that, which is exactly how this
        # broke in production without a failing test catching it first.
        assert system[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        assert system[1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        assert "THINGS TO REMEMBER ABOUT THIS USER" in system[0]["text"]
        assert "Keeps answers short." in system[0]["text"]
        # Not duplicated into the dynamic_context block
        assert "THINGS TO REMEMBER" not in system[1]["text"]


class TestMessageHistoryCaching:
    """The `messages` array (conversation history) wasn't cached at all before — only
    the system blocks were. A breakpoint on the last message that was already sent
    last turn (never on the new one, which changes every request) lets a growing
    conversation read history from cache instead of resending it as fresh tokens."""

    def test_last_prior_message_gets_cache_control_new_message_does_not(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("First reply."):
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "first message", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        with _mock_google_token(), _mock_anthropic_stream("Second reply.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "second message", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        messages = mock_client.messages.stream.call_args.kwargs["messages"]
        # The new message is exactly the block that changes every request — a
        # breakpoint here would never get a cache hit, so it must stay plain.
        assert messages[-1]["content"] == "second message"
        # The message right before it (last turn's assistant reply) is the stable
        # prefix boundary — must carry the breakpoint, converted to content-block form.
        second_to_last = messages[-2]
        assert isinstance(second_to_last["content"], list)
        # 1h TTL — an active conversation with gaps under an hour now stays on one
        # write for its whole lifetime instead of re-writing the growing history
        # every time a gap exceeds the old 5-minute default.
        assert second_to_last["content"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        assert second_to_last["content"][0]["text"] == "First reply."

    def test_first_message_in_conversation_has_no_history_to_cache(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hi.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        messages = mock_client.messages.stream.call_args.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["content"] == "hi"


class TestCacheBlockSplit:
    """Real production evidence: for a user with 83 tracked tickers, the shared
    compact-list block was 71% of the whole dynamic_context — but switching between
    two DIFFERENT ticker-scoped conversations busted the cache for the entire thing,
    because the focus ticker's dossier used to be embedded inline at the START of
    that same block. The fix: focus dossier is its own LAST block (cache breakpoints
    match a prefix, not each block independently — anything after a differing block
    also cache-misses, so the shared content has to come first)."""

    def test_focus_dossier_is_the_last_block(self, client: TestClient, db_session):
        from datetime import date
        from models import StockAnalysis
        db_session.add(StockAnalysis(ticker="ZFOCUSCACHE", analysis_date=date.today(), verdict="BUY", current_price=50.0))
        db_session.commit()

        conv_id = _create_conversation(client, ticker="ZFOCUSCACHE")
        with _mock_google_token(), _mock_anthropic_stream("Hi.") as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        system = mock_client.messages.stream.call_args.kwargs["system"]
        assert "ZFOCUSCACHE — FULL ANALYSIS" in system[-1]["text"]
        assert "ACTIVE CONVERSATION TOPIC: ZFOCUSCACHE" in system[-1]["text"]
        # And the block(s) before it must NOT contain the dossier — that's the split
        for block in system[:-1]:
            assert "FULL ANALYSIS" not in block["text"]

    def test_shared_block_is_byte_identical_across_different_ticker_conversations(self, client: TestClient, db_session):
        """The actual claim being tested: switching from one ticker-scoped conversation
        to a completely different one must NOT change the shared block's content, so
        Anthropic's exact-prefix cache match still hits for it."""
        from datetime import date
        from models import StockAnalysis, WatchlistItem
        e = "cacheswitcher@example.com"
        db_session.add(StockAnalysis(ticker="ZCACHEA", analysis_date=date.today(), verdict="BUY", current_price=10.0))
        db_session.add(StockAnalysis(ticker="ZCACHEB", analysis_date=date.today(), verdict="SELL", current_price=20.0))
        db_session.add(WatchlistItem(user_email=e, ticker="ZCACHEA"))
        db_session.add(WatchlistItem(user_email=e, ticker="ZCACHEB"))
        db_session.commit()

        conv_a = _create_conversation(client, ticker="ZCACHEA", email=e)
        with _mock_google_token(e), _mock_anthropic_stream("Hi.") as mock_client_a:
            client.post(
                f"/conversations/{conv_a}/messages/stream",
                json={"content": "hi", "user_email": e, "id_token": "tok"},
            )
        system_a = mock_client_a.messages.stream.call_args.kwargs["system"]

        conv_b = _create_conversation(client, ticker="ZCACHEB", email=e)
        with _mock_google_token(e), _mock_anthropic_stream("Hi.") as mock_client_b:
            client.post(
                f"/conversations/{conv_b}/messages/stream",
                json={"content": "hi", "user_email": e, "id_token": "tok"},
            )
        system_b = mock_client_b.messages.stream.call_args.kwargs["system"]

        # Same number of blocks, same structure
        assert len(system_a) == len(system_b)
        # Every block EXCEPT the last (focus dossier) must be byte-identical between
        # the two different ticker-scoped conversations — that's what makes them
        # cache-shareable instead of each switch forcing a full fresh write.
        for block_a, block_b in zip(system_a[:-1], system_b[:-1]):
            assert block_a["text"] == block_b["text"]
        # The last block (focus dossier) SHOULD differ — that's the one legitimately
        # ticker-specific piece.
        assert system_a[-1]["text"] != system_b[-1]["text"]
        assert "ZCACHEA" in system_a[-1]["text"]
        assert "ZCACHEB" in system_b[-1]["text"]

    def test_shared_block_includes_focus_tickers_own_compact_line(self, client: TestClient, db_session):
        """Confirms the mechanism: the focus ticker is no longer excluded from its own
        compact line in the shared block — that's what makes the shared block's
        content independent of which ticker happens to be in focus."""
        from datetime import date
        from models import StockAnalysis, WatchlistItem
        e = "cacheself@example.com"
        db_session.add(StockAnalysis(ticker="ZSELFLINE", analysis_date=date.today(), verdict="HOLD", current_price=15.0))
        db_session.add(WatchlistItem(user_email=e, ticker="ZSELFLINE"))
        db_session.commit()

        conv_id = _create_conversation(client, ticker="ZSELFLINE", email=e)
        with _mock_google_token(e), _mock_anthropic_stream("Hi.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": e, "id_token": "tok"},
            )
        system = mock_client.messages.stream.call_args.kwargs["system"]
        shared_block = system[-2]["text"]  # the block just before the focus dossier
        assert "ZSELFLINE: HOLD" in shared_block


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
        # Called twice now: once for the conversation's own focus ticker (TSLA, built
        # as its own cache block), once for the ZPIVOT pivot via get_stock_analysis.
        assert spy.call_count == 2
        pivot_call = next(c for c in spy.call_args_list if c.args[0].upper() == "ZPIVOT")
        assert pivot_call.args[2] == "streamtest@example.com"
        # And the real function actually returned ZPIVOT's dossier (not a stub)
        pivot_results = [r for r in captured_results if "ZPIVOT" in r]
        assert len(pivot_results) == 1
        assert "ZPIVOT — FULL ANALYSIS" in pivot_results[0]
        assert "AI demand." in pivot_results[0]


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
        # And it's the MOST RECENT ones, not the oldest. The last historical message
        # (msg 29) carries the cache breakpoint, so its content is a block list, not
        # a plain string — extract the text either way.
        def _text_of(content):
            return content if isinstance(content, str) else content[0]["text"]
        contents = [_text_of(m["content"]) for m in sent_messages]
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


class TestTemporalContext:
    """Real production bug this addresses: conversations can span days/weeks (up to
    12 days between messages in real synced production data — 6.5% of all turns had
    over a day between them), but the model saw the whole history as one flat,
    undifferentiated block with zero sense of elapsed time. Confirmed cause of a real
    conversation where the model got confused about a user's timezone claim after a
    multi-message gap, with no anchor for how much time had actually passed."""

    def test_no_marker_for_a_normal_quick_reply(self):
        from datetime import datetime, timedelta
        from routers.streaming import _elapsed_str
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        assert _elapsed_str(t0, t0 + timedelta(minutes=2)) is None

    def test_hours_gap_formatted_in_hours(self):
        from datetime import datetime, timedelta
        from routers.streaming import _elapsed_str
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        assert _elapsed_str(t0, t0 + timedelta(hours=2, minutes=30)) == "2.5 hours later"

    def test_one_day_gap_uses_singular(self):
        from datetime import datetime, timedelta
        from routers.streaming import _elapsed_str
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        assert _elapsed_str(t0, t0 + timedelta(days=1)) == "1 day later, on 2026-01-02"

    def test_days_gap_includes_the_date(self):
        from datetime import datetime, timedelta
        from routers.streaming import _elapsed_str
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        assert _elapsed_str(t0, t0 + timedelta(days=3)) == "3 days later, on 2026-01-04"

    def test_real_12_day_gap_from_production_data(self):
        """The longest real gap found auditing real synced production conversations."""
        from datetime import datetime, timedelta
        from routers.streaming import _elapsed_str
        t0 = datetime(2026, 7, 11, 9, 0, 0)
        assert "12 days later" in _elapsed_str(t0, t0 + timedelta(days=12, hours=2))

    def test_gap_marker_appears_for_a_conversation_resumed_after_days(self, client: TestClient, db_session):
        from datetime import datetime, timedelta
        from models import Message
        conv_id = _create_conversation(client)
        old_time = datetime.utcnow() - timedelta(days=5)
        db_session.add(Message(conversation_id=conv_id, role="user", content="first message", created_at=old_time))
        db_session.add(Message(conversation_id=conv_id, role="assistant", content="first reply", created_at=old_time + timedelta(seconds=30)))
        db_session.commit()

        with _mock_google_token(), _mock_anthropic_stream("Welcome back.") as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "resuming after a while", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        messages = mock_client.messages.stream.call_args.kwargs["messages"]
        # New message was never part of the cached prefix anyway, so its gap is
        # computed live against right now, not a fixed timestamp.
        assert "days later" in messages[-1]["content"]

    def test_no_gap_marker_for_a_quick_followup(self, client: TestClient, db_session):
        from models import Message
        conv_id = _create_conversation(client)
        db_session.add(Message(conversation_id=conv_id, role="user", content="first"))
        db_session.add(Message(conversation_id=conv_id, role="assistant", content="reply"))
        db_session.commit()

        with _mock_google_token(), _mock_anthropic_stream("Sure.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "quick followup", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        messages = mock_client.messages.stream.call_args.kwargs["messages"]
        assert "later" not in messages[-1]["content"]

    def test_history_is_byte_identical_no_matter_when_its_built(self):
        """The actual cache-safety claim, proven directly: the SAME historical prefix
        must produce identical text regardless of how much real time has passed since —
        only possible because gaps are computed from two fixed timestamps, never "now"."""
        from datetime import datetime, timedelta
        from models import Message
        from routers.streaming import _build_live_history
        import time

        t0 = datetime(2026, 1, 1, 9, 0, 0)
        rows = [
            Message(conversation_id="x", role="user", content="first", created_at=t0),
            Message(conversation_id="x", role="assistant", content="reply", created_at=t0 + timedelta(days=4)),
        ]
        first_build = _build_live_history(rows, rows)
        time.sleep(0.05)  # simulate real time passing between two "requests"
        second_build = _build_live_history(rows, rows)
        assert first_build == second_build
        assert "4 days later" in first_build[1]["content"]

    def test_first_live_row_gets_gap_against_trimmed_off_predecessor(self):
        """Edge case: the oldest message still in the live window may itself have a
        real gap from whatever got trimmed off — that predecessor isn't in live_rows,
        only in the full history_rows, so it has to be looked up there."""
        from datetime import datetime, timedelta
        from models import Message
        from routers.streaming import _build_live_history

        t0 = datetime(2026, 1, 1, 9, 0, 0)
        trimmed = Message(conversation_id="x", role="user", content="trimmed off", created_at=t0)
        kept = Message(conversation_id="x", role="assistant", content="still live", created_at=t0 + timedelta(days=6))
        history_rows = [trimmed, kept]
        live_rows = [kept]
        result = _build_live_history(history_rows, live_rows)
        assert "6 days later" in result[0]["content"]

    def test_get_chat_history_notes_how_long_ago_retrieved_messages_are(self, client: TestClient, db_session):
        from datetime import datetime, timedelta
        from models import Message
        conv_id = _create_conversation(client)
        for i in range(25):
            db_session.add(Message(
                conversation_id=conv_id, role="user", content=f"old message {i}",
                created_at=datetime.utcnow() - timedelta(days=10) + timedelta(minutes=i),
            ))
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
        assert "days ago" in tool_result_content


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

    def test_ticker_scoped_save_sets_ticker_column(self, client: TestClient, db_session):
        from models import UserLearning
        conv_id = _create_conversation(client, ticker="SLV")
        with _mock_google_token(), \
             _mock_anthropic_stream("", tool_use={
                 "name": "save_learning",
                 "input": {"learning": "Already knows SLV/GLD overlap, don't re-explain.", "ticker": "slv"},
             }) as mock_client:
            _make_second_call_end_turn(mock_client)
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "remember I know SLV/GLD overlap", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        row = db_session.query(UserLearning).filter(
            UserLearning.user_email == "streamtest@example.com", UserLearning.ticker == "SLV",
        ).first()
        assert row is not None
        assert row.learning == "Already knows SLV/GLD overlap, don't re-explain."

    def test_no_ticker_saves_as_global(self, client: TestClient, db_session):
        from models import UserLearning
        conv_id = _create_conversation(client)
        with _mock_google_token(), \
             _mock_anthropic_stream("", tool_use={"name": "save_learning", "input": {"learning": "Keeps answers short."}}) as mock_client:
            _make_second_call_end_turn(mock_client)
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "remember to keep it short", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        row = db_session.query(UserLearning).filter(
            UserLearning.user_email == "streamtest@example.com", UserLearning.learning == "Keeps answers short.",
        ).first()
        assert row is not None
        assert row.ticker is None


class TestDeleteLearningTool:
    def test_tool_is_offered(self, client: TestClient):
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hi.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        names = {t["name"] for t in mock_client.messages.stream.call_args.kwargs["tools"]}
        assert "delete_learning" in names

    def test_deletes_exact_match(self, client: TestClient, db_session):
        from models import UserLearning
        db_session.add(UserLearning(user_email="deleter@example.com", learning="Wrong fact to remove."))
        db_session.commit()

        conv_id = _create_conversation(client, email="deleter@example.com")
        with _mock_google_token("deleter@example.com"), \
             _mock_anthropic_stream("", tool_use={"name": "delete_learning", "input": {"learning": "Wrong fact to remove."}}) as mock_client:
            _make_second_call_end_turn(mock_client)
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "forget that", "user_email": "deleter@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        assert db_session.query(UserLearning).filter(
            UserLearning.user_email == "deleter@example.com", UserLearning.learning == "Wrong fact to remove.",
        ).count() == 0

    def test_no_fuzzy_match_deletes_nothing(self, client: TestClient, db_session):
        """Exact match only — a close-but-not-exact string must not delete the wrong
        learning. Deleting the wrong one silently is worse than doing nothing."""
        from models import UserLearning
        db_session.add(UserLearning(user_email="nofuzzy@example.com", learning="Manages 48 stocks total."))
        db_session.commit()

        conv_id = _create_conversation(client, email="nofuzzy@example.com")
        with _mock_google_token("nofuzzy@example.com"), \
             _mock_anthropic_stream("", tool_use={"name": "delete_learning", "input": {"learning": "manages 48 stocks"}}) as mock_client:
            _make_second_call_end_turn(mock_client)
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "forget the stock count thing", "user_email": "nofuzzy@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        assert db_session.query(UserLearning).filter(
            UserLearning.user_email == "nofuzzy@example.com", UserLearning.learning == "Manages 48 stocks total.",
        ).count() == 1


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


def _two_turn_stream_ctx(events, final_msg):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=ctx)
    ctx.__aexit__ = AsyncMock(return_value=False)

    async def _aiter(_self):
        for e in events:
            yield e
    ctx.__aiter__ = _aiter
    ctx.get_final_message = AsyncMock(return_value=final_msg)
    return ctx


class TestHeartbeat:
    """Regression, reproduced live: a genuine thinking phase left a 32.8s gap with only
    one event fired at its very start — landing inside ChatClient.tsx's 30s no-event
    watchdog and killing a request that was about to succeed. A slow-but-alive wait must
    emit periodic heartbeat events so the frontend's watchdog (which resets on ANY event
    type) never mistakes "still working" for "connection dropped"."""

    def test_heartbeat_emitted_during_a_slow_gap_between_events(self, client: TestClient, db_session, monkeypatch):
        import asyncio
        monkeypatch.setattr("routers.streaming._HEARTBEAT_INTERVAL_SECONDS", 0.05)

        text_delta = MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="Done thinking."))
        final_msg = MagicMock(stop_reason="end_turn", content=[],
                               usage=MagicMock(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0))

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)

        async def _aiter(_self):
            await asyncio.sleep(0.2)  # well past the patched 0.05s heartbeat interval
            yield text_delta
        ctx.__aiter__ = _aiter
        ctx.get_final_message = AsyncMock(return_value=final_msg)

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=ctx)
        mock_client.messages.create = AsyncMock(return_value=MagicMock(content=[MagicMock(text="Title")]))

        conv_id = _create_conversation(client)
        with _mock_google_token(), patch("routers.streaming.anthropic.AsyncAnthropic", return_value=mock_client):
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )

        assert r.status_code == 200
        heartbeats = [line for line in r.text.splitlines() if '"type": "heartbeat"' in line]
        assert len(heartbeats) >= 1

    def test_no_heartbeats_when_events_arrive_quickly(self, client: TestClient, db_session):
        """The common case — no artificial delay — must never emit a heartbeat."""
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Quick reply.") as _mc:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        assert '"type": "heartbeat"' not in r.text


class TestTurnSeparator:
    """Regression for issue #118: full_text += chunk never distinguished a turn
    boundary (text -> tool_use -> tool_result -> more text) from a mid-sentence chunk
    boundary, so two turns' text ran together with zero separator
    ("...one sec.Only XLP..."). Full custom two-call mock — the shared
    _mock_anthropic_stream helper only ever puts text in one branch (tool_use XOR
    text), never both, so it can't represent a turn that has lead-in text before
    calling a tool."""

    def test_separator_inserted_between_tool_loop_turns(self, client: TestClient, db_session):
        from models import Message

        conv_id = _create_conversation(client)

        turn1_text = MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="Yes — pulling now, one sec."))
        tool_start = MagicMock(type="content_block_start")
        # `name=` in the MagicMock() constructor sets the mock's own repr, not a real
        # .name attribute — must assign it directly or current_tool_name never populates.
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tu_1"
        tool_block.name = "get_stock_analysis"
        tool_start.content_block = tool_block
        tool_input = MagicMock(type="content_block_delta", delta=MagicMock(type="input_json_delta", partial_json='{"ticker": "XLP"}'))
        tool_stop = MagicMock(type="content_block_stop")
        turn1_final = MagicMock(stop_reason="tool_use", content=[],
                                 usage=MagicMock(input_tokens=50, output_tokens=10, cache_read_input_tokens=0, cache_creation_input_tokens=0))

        turn2_text = MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="Only XLP is in our own database."))
        turn2_final = MagicMock(stop_reason="end_turn", content=[],
                                 usage=MagicMock(input_tokens=20, output_tokens=8, cache_read_input_tokens=0, cache_creation_input_tokens=0))

        turns = [
            ([turn1_text, tool_start, tool_input, tool_stop], turn1_final),
            ([turn2_text], turn2_final),
        ]
        call_count = {"n": 0}

        def _side_effect(**kwargs):
            events, final_msg = turns[call_count["n"]]
            call_count["n"] += 1
            return _two_turn_stream_ctx(events, final_msg)

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(side_effect=_side_effect)
        mock_client.messages.create = AsyncMock(return_value=MagicMock(content=[MagicMock(text="Title")]))

        with _mock_google_token(), \
             patch("routers.streaming.anthropic.AsyncAnthropic", return_value=mock_client), \
             patch("routers.streaming.build_ticker_dossier", return_value="dossier text"):
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "compare sector ETFs", "user_email": "streamtest@example.com", "id_token": "tok"},
            )

        assert r.status_code == 200
        db_session.expire_all()
        msg = db_session.query(Message).filter(Message.conversation_id == conv_id, Message.role == "assistant").first()
        assert msg is not None
        assert "one sec.\n\nOnly XLP" in msg.content
        assert "sec.Only" not in msg.content  # the exact regression this guards against

    def test_streamed_chunk_carries_the_separator_live(self, client: TestClient, db_session):
        """Not just the persisted row — the client must also see the separator while
        the response is actively streaming, since ChatClient accumulates chunks the
        same concatenating way full_text does."""
        turn1_text = MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="Lead-in."))
        tool_start = MagicMock(type="content_block_start")
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tu_1"
        tool_block.name = "get_stock_analysis"
        tool_start.content_block = tool_block
        tool_input = MagicMock(type="content_block_delta", delta=MagicMock(type="input_json_delta", partial_json='{"ticker": "XLP"}'))
        tool_stop = MagicMock(type="content_block_stop")
        turn1_final = MagicMock(stop_reason="tool_use", content=[],
                                 usage=MagicMock(input_tokens=50, output_tokens=10, cache_read_input_tokens=0, cache_creation_input_tokens=0))
        turn2_text = MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="Follow-up."))
        turn2_final = MagicMock(stop_reason="end_turn", content=[],
                                 usage=MagicMock(input_tokens=20, output_tokens=8, cache_read_input_tokens=0, cache_creation_input_tokens=0))
        turns = [([turn1_text, tool_start, tool_input, tool_stop], turn1_final), ([turn2_text], turn2_final)]
        call_count = {"n": 0}

        def _side_effect(**kwargs):
            events, final_msg = turns[call_count["n"]]
            call_count["n"] += 1
            return _two_turn_stream_ctx(events, final_msg)

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(side_effect=_side_effect)
        mock_client.messages.create = AsyncMock(return_value=MagicMock(content=[MagicMock(text="Title")]))

        conv_id = _create_conversation(client)
        with _mock_google_token(), \
             patch("routers.streaming.anthropic.AsyncAnthropic", return_value=mock_client), \
             patch("routers.streaming.build_ticker_dossier", return_value="dossier text"):
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "compare sector ETFs", "user_email": "streamtest@example.com", "id_token": "tok"},
            )

        chunks = [json.loads(line[6:])["text"] for line in r.text.splitlines()
                  if line.startswith("data: ") and '"type": "chunk"' in line]
        assert chunks == ["Lead-in.", "\n\n", "Follow-up."]


class TestTruncatedResponseMarker:
    """Regression for issue #118: persist() saved full_text unconditionally from the
    except/finally paths, so a reply cut short mid-turn (dropped connection, API
    error) was stored and later displayed identically to a genuinely complete one."""

    def test_exception_mid_stream_persists_with_truncation_marker(self, client: TestClient, db_session):
        from models import Message

        text_delta = MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="Partial thought that never finishes"))

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)

        async def _aiter(_self):
            yield text_delta
            raise ConnectionError("simulated drop")
        ctx.__aiter__ = _aiter
        ctx.get_final_message = AsyncMock()  # never reached — the raise happens first

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=ctx)
        # Title generation kicks off as a background task before the stream errors —
        # give it a real awaitable or it logs an unretrieved-exception warning.
        mock_client.messages.create = AsyncMock(return_value=MagicMock(content=[MagicMock(text="Title")]))

        conv_id = _create_conversation(client)
        with _mock_google_token(), patch("routers.streaming.anthropic.AsyncAnthropic", return_value=mock_client):
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )

        assert r.status_code == 200  # the SSE stream itself still opens fine
        db_session.expire_all()
        msg = db_session.query(Message).filter(Message.conversation_id == conv_id, Message.role == "assistant").first()
        assert msg is not None
        assert msg.content.startswith("Partial thought that never finishes")
        assert "[Response interrupted" in msg.content

    def test_clean_end_turn_gets_no_truncation_marker(self, client: TestClient, db_session):
        from models import Message
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("A complete reply.") as _mc:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        db_session.expire_all()
        msg = db_session.query(Message).filter(Message.conversation_id == conv_id, Message.role == "assistant").first()
        assert msg is not None
        assert msg.content == "A complete reply."
        assert "[Response interrupted" not in msg.content

    def test_max_tokens_with_zero_visible_text_still_persists(self, client: TestClient, db_session):
        """Regression, reproduced live: a turn can hit max_tokens while still inside
        thinking/an unfinished tool call, before any text_delta ever fires — full_text
        stays "" even though the turn cost real tokens. persist() used to no-op
        entirely on empty full_text, so this vanished with nothing in the DB and
        nothing in the logs. A turn that spent tokens must always leave a trace."""
        from models import Message

        final = MagicMock(
            stop_reason="max_tokens", content=[MagicMock(type="thinking")],
            usage=MagicMock(input_tokens=9000, output_tokens=2048, cache_read_input_tokens=0, cache_creation_input_tokens=0),
        )
        ctx = _two_turn_stream_ctx([], final)  # no text_delta events at all

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=ctx)
        mock_client.messages.create = AsyncMock(return_value=MagicMock(content=[MagicMock(text="Title")]))

        conv_id = _create_conversation(client)
        with _mock_google_token(), patch("routers.streaming.anthropic.AsyncAnthropic", return_value=mock_client):
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )

        assert r.status_code == 200
        db_session.expire_all()
        msg = db_session.query(Message).filter(Message.conversation_id == conv_id, Message.role == "assistant").first()
        assert msg is not None
        assert "[Response interrupted" in msg.content
        assert msg.output_tokens == 2048


class TestMaxTokensAutoContinuation:
    """Regression, reproduced against real production data: a 94-ticker watchlist's
    ~40k-token system prompt was large enough that Sonnet 5 spent the majority of
    max_tokens on its own unprompted reasoning before any visible text — even for
    messages that never requested thinking. A stop_reason=max_tokens response with no
    tool call used to be silently misclassified as a clean finish (the old
    `not tool_uses` check didn't distinguish it from a genuine end_turn), so a reply
    cut off mid-sentence looked identical to a complete answer, or — when zero text
    survived — vanished with nothing saved at all."""

    def test_max_tokens_with_trailing_text_triggers_one_continuation(self, client: TestClient, db_session):
        from models import Message

        turn1_text = MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="This needs assumed rates of"))
        turn1_block = MagicMock(type="text", text="This needs assumed rates of")
        turn1_final = MagicMock(stop_reason="max_tokens", content=[turn1_block],
                                 usage=MagicMock(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0))

        turn2_text = MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text=" return, which I'll assume conservatively."))
        turn2_final = MagicMock(stop_reason="end_turn", content=[],
                                 usage=MagicMock(input_tokens=120, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0))

        turns = [([turn1_text], turn1_final), ([turn2_text], turn2_final)]
        call_count = {"n": 0}

        def _side_effect(**kwargs):
            events, final_msg = turns[call_count["n"]]
            call_count["n"] += 1
            return _two_turn_stream_ctx(events, final_msg)

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(side_effect=_side_effect)
        mock_client.messages.create = AsyncMock(return_value=MagicMock(content=[MagicMock(text="Title")]))

        conv_id = _create_conversation(client)
        with _mock_google_token(), patch("routers.streaming.anthropic.AsyncAnthropic", return_value=mock_client):
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "predict my return", "user_email": "streamtest@example.com", "id_token": "tok"},
            )

        assert r.status_code == 200
        assert call_count["n"] == 2  # exactly one continuation — no more, no less
        db_session.expire_all()
        msg = db_session.query(Message).filter(Message.conversation_id == conv_id, Message.role == "assistant").first()
        assert msg is not None
        # Seamless — no "\n\n" turn-separator inserted mid-sentence, unlike the tool-use case
        assert msg.content == "This needs assumed rates of return, which I'll assume conservatively."
        assert "[Response interrupted" not in msg.content

        second_call_messages = mock_client.messages.stream.call_args_list[1].kwargs["messages"]
        assert second_call_messages[-2]["role"] == "assistant"
        assert second_call_messages[-1]["role"] == "user"
        assert "Continue your previous answer" in second_call_messages[-1]["content"]

    def test_repeated_max_tokens_stops_after_bound_and_marks_interrupted(self, client: TestClient, db_session):
        """Never loops forever — capped at _MAX_CONTINUATION_ATTEMPTS, then falls back
        to the honest truncation marker rather than retrying indefinitely."""
        from models import Message
        from routers.streaming import _MAX_CONTINUATION_ATTEMPTS

        def _make_turn(text):
            delta = MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text=text))
            block = MagicMock(type="text", text=text)
            final = MagicMock(stop_reason="max_tokens", content=[block],
                               usage=MagicMock(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0))
            return ([delta], final)

        # Every single turn hits max_tokens again — the pathological case.
        turns = [_make_turn(f"chunk{i} ") for i in range(_MAX_CONTINUATION_ATTEMPTS + 5)]
        call_count = {"n": 0}

        def _side_effect(**kwargs):
            events, final_msg = turns[call_count["n"]]
            call_count["n"] += 1
            return _two_turn_stream_ctx(events, final_msg)

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(side_effect=_side_effect)
        mock_client.messages.create = AsyncMock(return_value=MagicMock(content=[MagicMock(text="Title")]))

        conv_id = _create_conversation(client)
        with _mock_google_token(), patch("routers.streaming.anthropic.AsyncAnthropic", return_value=mock_client):
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )

        assert r.status_code == 200
        # Original attempt + exactly _MAX_CONTINUATION_ATTEMPTS retries, never more.
        assert call_count["n"] == _MAX_CONTINUATION_ATTEMPTS + 1
        db_session.expire_all()
        msg = db_session.query(Message).filter(Message.conversation_id == conv_id, Message.role == "assistant").first()
        assert msg is not None
        assert "[Response interrupted" in msg.content

    def test_max_tokens_ending_in_tool_use_does_not_attempt_continuation(self, client: TestClient, db_session):
        """A truncated tool_use/server_tool_use block is a genuinely harder problem
        (resuming a half-issued tool call safely) — deliberately out of scope here.
        Must fall straight through to the truncation marker instead of guessing."""
        from models import Message

        text_delta = MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="Let me check that."))
        text_block = MagicMock(type="text", text="Let me check that.")
        tool_block = MagicMock(type="server_tool_use")
        final = MagicMock(stop_reason="max_tokens", content=[text_block, tool_block],
                           usage=MagicMock(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0))

        ctx = _two_turn_stream_ctx([text_delta], final)
        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=ctx)
        mock_client.messages.create = AsyncMock(return_value=MagicMock(content=[MagicMock(text="Title")]))

        conv_id = _create_conversation(client)
        with _mock_google_token(), patch("routers.streaming.anthropic.AsyncAnthropic", return_value=mock_client):
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )

        assert r.status_code == 200
        assert mock_client.messages.stream.call_count == 1  # no continuation attempted
        db_session.expire_all()
        msg = db_session.query(Message).filter(Message.conversation_id == conv_id, Message.role == "assistant").first()
        assert msg is not None
        assert "[Response interrupted" in msg.content

    def test_normal_end_turn_never_touches_continuation_logic(self, client: TestClient, db_session):
        """The zero-added-cost claim for the common case: a normal reply makes exactly
        one .stream() call, same as before this fix existed."""
        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Normal reply.") as mock_client:
            r = client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        assert r.status_code == 200
        assert mock_client.messages.stream.call_count == 1


class TestMaxTokensFlatBudget:
    """Regression: a literal "hi" deep in a real, heavily-loaded production
    conversation burned through thinking tokens with zero visible text — the
    reasoning load comes from the conversation, not the new message, so
    _estimate_max_tokens no longer tiers by message length (see its comment).
    Both a trivial and a substantive message must get the same full budget."""

    def test_short_message_gets_the_full_budget(self, client: TestClient, db_session):
        from services.model_router import _estimate_max_tokens

        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Hi there.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": "hi", "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        used_max_tokens = mock_client.messages.stream.call_args.kwargs["max_tokens"]
        assert used_max_tokens == _estimate_max_tokens("hi") == 8192

    def test_longer_message_gets_the_same_full_budget(self, client: TestClient, db_session):
        from services.model_router import _estimate_max_tokens
        message = "please explain this in detail"

        conv_id = _create_conversation(client)
        with _mock_google_token(), _mock_anthropic_stream("Sure.") as mock_client:
            client.post(
                f"/conversations/{conv_id}/messages/stream",
                json={"content": message, "user_email": "streamtest@example.com", "id_token": "tok"},
            )
        used_max_tokens = mock_client.messages.stream.call_args.kwargs["max_tokens"]
        assert used_max_tokens == _estimate_max_tokens(message) == 8192
