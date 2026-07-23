"""
Tests for agents/ripple_agent.py — the usage-tracking crash this session found and
fixed: a June 28 refactor renamed the real model call from Sonnet to Haiku but left
two usage dicts referencing the now-undefined _SONNET. The Haiku call succeeded and
was billed for real every night, then the function crashed building its own return
value (NameError) immediately after — caught by nightly_runner's broad except, which
silently discarded the real ripple text and substituted a placeholder. Ran this way,
undetected, for about a month.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.ripple_agent import _HAIKU, analyze_ripple


def _mock_anthropic(text: str, input_tokens=100, output_tokens=50, cache_read=20, cache_write=5):
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(
        input_tokens=input_tokens, output_tokens=output_tokens,
        cache_read_input_tokens=cache_read, cache_write_input_tokens=cache_write,
    )
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=resp)
    return client


class TestAnalyzeRipple:
    @pytest.mark.asyncio
    async def test_real_call_returns_usage_without_crashing(self, monkeypatch):
        """The actual regression: this used to raise NameError on the return path
        even though the Haiku call itself had already succeeded and been billed."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock = _mock_anthropic("  Some ripple text.  ")
        with patch("agents.ripple_agent.anthropic.AsyncAnthropic", return_value=mock):
            text, usage = await analyze_ripple("NVDA", "Some real news summary.")
        assert text == "Some ripple text."
        assert usage == {
            "input_tokens": 100, "output_tokens": 50,
            "cache_read": 20, "cache_write": 5, "model": _HAIKU,
        }

    @pytest.mark.asyncio
    async def test_uses_haiku_for_the_real_call(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock = _mock_anthropic("Some ripple text.")
        with patch("agents.ripple_agent.anthropic.AsyncAnthropic", return_value=mock):
            await analyze_ripple("NVDA", "Some real news summary.")
        assert mock.messages.create.call_args.kwargs["model"] == _HAIKU

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_empty_usage_without_crashing(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        text, usage = await analyze_ripple("NVDA", "Some real news summary.")
        assert usage == {"input_tokens": 0, "output_tokens": 0, "cache_read": 0, "cache_write": 0, "model": _HAIKU}

    @pytest.mark.asyncio
    async def test_no_news_returns_empty_usage_without_crashing(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        text, usage = await analyze_ripple("NVDA", "No recent news found.")
        assert usage["model"] == _HAIKU
        assert usage["input_tokens"] == 0

    @pytest.mark.asyncio
    async def test_empty_news_string_returns_empty_usage_without_crashing(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        text, usage = await analyze_ripple("NVDA", "")
        assert usage["model"] == _HAIKU
