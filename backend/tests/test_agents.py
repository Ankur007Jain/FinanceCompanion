"""
Unit tests for agent helper functions.
No network calls — all pure logic.
"""
import json
import pytest
from agents.analyst_agent import _safe_float


class TestSafeFloat:
    def test_returns_float_for_valid_value(self):
        assert _safe_float({"pe": 25.5}, "pe") == pytest.approx(25.5)

    def test_returns_none_for_missing_key(self):
        assert _safe_float({}, "pe") is None

    def test_returns_none_for_none_value(self):
        assert _safe_float({"pe": None}, "pe") is None

    def test_returns_none_for_zero(self):
        assert _safe_float({"pe": 0}, "pe") is None

    def test_returns_none_for_zero_float(self):
        assert _safe_float({"pe": 0.0}, "pe") is None

    def test_coerces_string_number(self):
        assert _safe_float({"pe": "30.2"}, "pe") == pytest.approx(30.2)

    def test_returns_none_for_non_numeric_string(self):
        assert _safe_float({"pe": "N/A"}, "pe") is None

    def test_first_key_wins(self):
        result = _safe_float({"a": 1.5, "b": 2.5}, "a", "b")
        assert result == pytest.approx(1.5)

    def test_falls_through_to_second_key(self):
        result = _safe_float({"b": 2.5}, "a", "b")
        assert result == pytest.approx(2.5)

    def test_all_keys_missing_returns_none(self):
        assert _safe_float({"x": 1.0}, "a", "b", "c") is None

    def test_handles_integer_value(self):
        assert _safe_float({"cap": 1_000_000}, "cap") == pytest.approx(1_000_000.0)

    def test_negative_values_returned(self):
        assert _safe_float({"change": -0.05}, "change") == pytest.approx(-0.05)


class TestVerdictResult:
    def test_defaults(self):
        from agents.verdict_agent import VerdictResult
        v = VerdictResult(
            verdict="HOLD",
            entry_target=None,
            exit_target=None,
            stop_loss=None,
            hold_period=None,
            reasoning="Test",
            conflict_flags="",
        )
        assert v.is_important_day is False
        assert v.importance_reason == ""

    def test_important_day_flag(self):
        from agents.verdict_agent import VerdictResult
        v = VerdictResult(
            verdict="BUY",
            entry_target=100.0,
            exit_target=120.0,
            stop_loss=90.0,
            hold_period="2-4 weeks",
            reasoning="Earnings beat.",
            conflict_flags="",
            is_important_day=True,
            importance_reason="Earnings reversal",
        )
        assert v.is_important_day is True
        assert v.importance_reason == "Earnings reversal"


class TestYFDataSerialization:
    """Verify YFData can round-trip through JSON (used by market_data_cache)."""

    def test_yf_data_history_serialization(self):
        from agents.yf_fetcher import YFData
        import pandas as pd

        df = pd.DataFrame(
            {"Close": [100.0, 101.0], "Volume": [1_000_000, 1_100_000]},
            index=pd.date_range("2024-01-01", periods=2, freq="D"),
        )
        data = YFData(
            info={"symbol": "TEST", "marketCap": 500_000_000},
            history=df,
            news=[{"title": "Test news", "link": "http://example.com"}],
            calendar={},
        )
        assert data.info["symbol"] == "TEST"
        assert len(data.history) == 2
        assert len(data.news) == 1
