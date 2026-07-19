"""Tests for services/model_router.py — max_tokens tiering and the extended-thinking
trigger heuristic."""
from services.model_router import _estimate_max_tokens, _should_use_extended_thinking


class TestEstimateMaxTokens:
    def test_short_message_gets_small_budget(self):
        assert _estimate_max_tokens("no") == 1024

    def test_analytical_keyword_gets_large_budget(self):
        assert _estimate_max_tokens("can you analyze this") == 6000

    def test_default_budget(self):
        assert _estimate_max_tokens("what do you think about this stock") == 4096


class TestShouldUseExtendedThinking:
    def test_rebalance_triggers(self):
        assert _should_use_extended_thinking("should I rebalance my portfolio") is True

    def test_should_i_sell_triggers(self):
        assert _should_use_extended_thinking("should I sell MU right now") is True

    def test_across_all_stocks_triggers(self):
        assert _should_use_extended_thinking("what should I do across all my stocks") is True

    def test_simple_greeting_does_not_trigger(self):
        assert _should_use_extended_thinking("hi") is False

    def test_single_ticker_question_does_not_trigger(self):
        assert _should_use_extended_thinking("what's the RSI on NVDA") is False

    def test_case_insensitive(self):
        assert _should_use_extended_thinking("Should I REBALANCE now?") is True
