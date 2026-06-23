"""
Tests for _compute_signal_convergence — the deterministic Phase 2 scoring function.
No mocks needed: pure Python, no I/O.
"""
import pytest
from datetime import date, timedelta
from dataclasses import dataclass
from typing import Optional


# ── minimal stubs that match the dataclass interface ──────────────────────────

@dataclass
class _Price:
    rsi: Optional[float] = None
    range_position_pct: Optional[float] = None
    current_price: Optional[float] = None
    ma_200: Optional[float] = None


@dataclass
class _Analyst:
    upside_pct: Optional[float] = None
    free_cashflow: Optional[float] = None
    inst_ownership_pct: Optional[float] = None


# Import the function under test (backend package is on sys.path via conftest)
from services.nightly_runner import _compute_signal_convergence


# ── helpers ───────────────────────────────────────────────────────────────────

def _earnings_event(days_from_now: int) -> dict:
    d = (date.today() + timedelta(days=days_from_now)).isoformat()
    return {"date": d, "description": "Q2 Earnings Report"}


def _perfect_price() -> _Price:
    """All price-based signals fire."""
    return _Price(rsi=38.0, range_position_pct=20.0, current_price=95.0, ma_200=100.0)


def _perfect_analyst() -> _Analyst:
    """All analyst-based signals fire."""
    return _Analyst(upside_pct=20.0, free_cashflow=1_000_000_000, inst_ownership_pct=0.55)


# ── score correctness ─────────────────────────────────────────────────────────

class TestAllSignalsFire:
    def test_perfect_setup_scores_7(self):
        score, details = _compute_signal_convergence(
            _perfect_price(), _perfect_analyst(), []
        )
        assert score == 7
        assert all(details.values()), "Every signal should be True"

    def test_returns_tuple_of_int_and_dict(self):
        score, details = _compute_signal_convergence(_perfect_price(), _perfect_analyst(), [])
        assert isinstance(score, int)
        assert isinstance(details, dict)
        assert len(details) == 7


class TestIndividualSignals:
    def test_oversold_rsi_fires_below_42(self):
        p = _perfect_price()
        p.rsi = 41.9
        score, d = _compute_signal_convergence(p, _perfect_analyst(), [])
        assert d["oversold_rsi"] is True

    def test_oversold_rsi_does_not_fire_at_42(self):
        p = _perfect_price()
        p.rsi = 42.0
        _, d = _compute_signal_convergence(p, _perfect_analyst(), [])
        assert d["oversold_rsi"] is False

    def test_oversold_rsi_none_does_not_fire(self):
        p = _perfect_price()
        p.rsi = None
        _, d = _compute_signal_convergence(p, _perfect_analyst(), [])
        assert d["oversold_rsi"] is False

    def test_near_52w_low_fires_below_35pct(self):
        p = _perfect_price()
        p.range_position_pct = 34.9
        _, d = _compute_signal_convergence(p, _perfect_analyst(), [])
        assert d["near_52w_low"] is True

    def test_near_52w_low_does_not_fire_at_35(self):
        p = _perfect_price()
        p.range_position_pct = 35.0
        _, d = _compute_signal_convergence(p, _perfect_analyst(), [])
        assert d["near_52w_low"] is False

    def test_analyst_upside_fires_above_15(self):
        a = _perfect_analyst()
        a.upside_pct = 15.1
        _, d = _compute_signal_convergence(_perfect_price(), a, [])
        assert d["analyst_upside_15pct"] is True

    def test_analyst_upside_does_not_fire_at_15(self):
        a = _perfect_analyst()
        a.upside_pct = 15.0
        _, d = _compute_signal_convergence(_perfect_price(), a, [])
        assert d["analyst_upside_15pct"] is False

    def test_analyst_upside_none_does_not_fire(self):
        a = _perfect_analyst()
        a.upside_pct = None
        _, d = _compute_signal_convergence(_perfect_price(), a, [])
        assert d["analyst_upside_15pct"] is False

    def test_positive_fcf_fires_above_zero(self):
        a = _perfect_analyst()
        a.free_cashflow = 1
        _, d = _compute_signal_convergence(_perfect_price(), a, [])
        assert d["positive_fcf"] is True

    def test_positive_fcf_does_not_fire_at_zero(self):
        a = _perfect_analyst()
        a.free_cashflow = 0
        _, d = _compute_signal_convergence(_perfect_price(), a, [])
        assert d["positive_fcf"] is False

    def test_positive_fcf_does_not_fire_for_negative(self):
        a = _perfect_analyst()
        a.free_cashflow = -500_000_000
        _, d = _compute_signal_convergence(_perfect_price(), a, [])
        assert d["positive_fcf"] is False

    def test_institutional_backing_fires_above_40pct(self):
        a = _perfect_analyst()
        a.inst_ownership_pct = 0.41
        _, d = _compute_signal_convergence(_perfect_price(), a, [])
        assert d["institutional_backing"] is True

    def test_institutional_backing_does_not_fire_at_40pct(self):
        a = _perfect_analyst()
        a.inst_ownership_pct = 0.40
        _, d = _compute_signal_convergence(_perfect_price(), a, [])
        assert d["institutional_backing"] is False

    def test_price_stabilizing_fires_within_10pct_of_ma200(self):
        p = _perfect_price()
        p.current_price = 91.0   # 91 / 100 = 91% of MA200 → ≥ 90%
        p.ma_200 = 100.0
        _, d = _compute_signal_convergence(p, _perfect_analyst(), [])
        assert d["price_stabilizing"] is True

    def test_price_stabilizing_does_not_fire_more_than_10pct_below_ma200(self):
        p = _perfect_price()
        p.current_price = 89.0   # 89 / 100 = 89% → below 90% threshold
        p.ma_200 = 100.0
        _, d = _compute_signal_convergence(p, _perfect_analyst(), [])
        assert d["price_stabilizing"] is False

    def test_price_stabilizing_none_ma200_does_not_fire(self):
        p = _perfect_price()
        p.ma_200 = None
        _, d = _compute_signal_convergence(p, _perfect_analyst(), [])
        assert d["price_stabilizing"] is False


class TestEarningsProximity:
    def test_no_binary_risk_fires_with_no_events(self):
        _, d = _compute_signal_convergence(_perfect_price(), _perfect_analyst(), [])
        assert d["no_binary_risk"] is True

    def test_no_binary_risk_fires_when_earnings_22_days_out(self):
        _, d = _compute_signal_convergence(
            _perfect_price(), _perfect_analyst(), [_earnings_event(22)]
        )
        assert d["no_binary_risk"] is True

    def test_no_binary_risk_blocked_when_earnings_within_21_days(self):
        _, d = _compute_signal_convergence(
            _perfect_price(), _perfect_analyst(), [_earnings_event(21)]
        )
        assert d["no_binary_risk"] is False

    def test_no_binary_risk_blocked_when_earnings_tomorrow(self):
        _, d = _compute_signal_convergence(
            _perfect_price(), _perfect_analyst(), [_earnings_event(1)]
        )
        assert d["no_binary_risk"] is False

    def test_non_earnings_event_does_not_block(self):
        event = {"date": (date.today() + timedelta(days=5)).isoformat(), "description": "Fed rate decision"}
        _, d = _compute_signal_convergence(_perfect_price(), _perfect_analyst(), [event])
        assert d["no_binary_risk"] is True

    def test_earnings_keyword_q3_detected(self):
        event = {"date": (date.today() + timedelta(days=10)).isoformat(), "description": "Q3 results release"}
        _, d = _compute_signal_convergence(_perfect_price(), _perfect_analyst(), [event])
        assert d["no_binary_risk"] is False

    def test_past_earnings_not_counted(self):
        # Negative days — in the past
        event = {"date": (date.today() - timedelta(days=5)).isoformat(), "description": "Earnings Q1"}
        _, d = _compute_signal_convergence(_perfect_price(), _perfect_analyst(), [event])
        assert d["no_binary_risk"] is True

    def test_malformed_event_date_skipped(self):
        event = {"date": "not-a-date", "description": "Earnings"}
        score, d = _compute_signal_convergence(_perfect_price(), _perfect_analyst(), [event])
        assert d["no_binary_risk"] is True  # gracefully skipped, no crash


class TestScoreSummation:
    def test_score_equals_count_of_true_signals(self):
        score, details = _compute_signal_convergence(_perfect_price(), _perfect_analyst(), [])
        assert score == sum(1 for v in details.values() if v)

    def test_zero_score_for_all_bad_inputs(self):
        p = _Price(rsi=75, range_position_pct=80, current_price=50, ma_200=100)
        a = _Analyst(upside_pct=5, free_cashflow=-1_000_000, inst_ownership_pct=0.10)
        score, details = _compute_signal_convergence(p, a, [_earnings_event(5)])
        assert score == 0
        assert not any(details.values())

    def test_partial_score_counts_correctly(self):
        # Only rsi and no_binary_risk fire
        p = _Price(rsi=30, range_position_pct=60, current_price=50, ma_200=100)
        a = _Analyst(upside_pct=5, free_cashflow=-1, inst_ownership_pct=0.10)
        score, details = _compute_signal_convergence(p, a, [])
        assert details["oversold_rsi"] is True
        assert details["no_binary_risk"] is True
        assert score == 2
