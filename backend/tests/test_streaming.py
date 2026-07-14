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


@contextmanager
def _mock_anthropic_stream(text: str = "Test reply.", tool_use: dict | None = None):
    """tool_use, if given ({"name": ..., "input": {...}}), makes the mocked stream emit one
    tool_use block before ending (stop_reason=tool_use), so the second loop iteration can
    be asserted on too. Without it, a plain end_turn text reply."""
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
    final_msg.content = []

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


def _create_conversation(client: TestClient, ticker: str | None = None):
    with _mock_google_token():
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
        assert len(system) == 2
        assert system[0]["cache_control"] == {"type": "ephemeral"}
        assert system[1]["cache_control"] == {"type": "ephemeral"}


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
