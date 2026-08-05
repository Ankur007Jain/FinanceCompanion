"""
Tests for the long-term/short-term horizon skip-check
(scripts/should_recompute_horizon.py). Pure function, no I/O.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from should_recompute_horizon import should_recompute  # noqa: E402

TODAY = date(2026, 8, 4)


def _prior(**overrides):
    base = {
        "time_horizon_fit": "LONG_TERM_HOLD",
        "time_horizon_reasoning": "Durable moat, strong balance sheet.",
        "time_horizon_last_computed": "2026-06-01",
        "analyst_consensus": "BUY",
        "pe_forward": 20.0,
        "revenue_growth": 0.10,
        "earnings_growth": 0.15,
        "profit_margin": 0.20,
        "debt_to_equity": 50.0,
        "market_cap": 1_000_000_000,
    }
    base.update(overrides)
    return base


def _now(**overrides):
    base = {
        "analyst": "BUY",
        "pe_forward": 20.0,
        "revenue_growth": 0.10,
        "earnings_growth": 0.15,
        "profit_margin": 0.20,
        "debt_to_equity": 50.0,
        "market_cap": 1_000_000_000,
    }
    base.update(overrides)
    return base


class TestNoPriorJudgment:
    def test_never_computed_always_recomputes(self):
        result = should_recompute(_now(), None, today=TODAY)
        assert result["should_recompute"] is True
        assert "No prior" in result["reason"]


class TestUnchangedFundamentals:
    def test_identical_fundamentals_reuses_prior(self):
        result = should_recompute(_now(), _prior(), today=TODAY)
        assert result["should_recompute"] is False
        assert result["reused_fit"] == "LONG_TERM_HOLD"
        assert result["reused_reasoning"] == "Durable moat, strong balance sheet."


class TestStaleness:
    def test_over_90_days_forces_recompute(self):
        prior = _prior(time_horizon_last_computed="2026-04-01")  # 125 days before TODAY
        result = should_recompute(_now(), prior, today=TODAY)
        assert result["should_recompute"] is True
        assert "Staleness" in result["reason"]

    def test_under_90_days_does_not_force_recompute(self):
        prior = _prior(time_horizon_last_computed="2026-06-01")  # 64 days before TODAY
        result = should_recompute(_now(), prior, today=TODAY)
        assert result["should_recompute"] is False

    def test_no_prior_computed_date_skips_staleness_check(self):
        prior = _prior(time_horizon_last_computed=None)
        result = should_recompute(_now(), prior, today=TODAY)
        assert result["should_recompute"] is False


class TestAnalystConsensusChange:
    def test_consensus_flip_forces_recompute(self):
        result = should_recompute(_now(analyst="SELL"), _prior(analyst_consensus="BUY"), today=TODAY)
        assert result["should_recompute"] is True
        assert "Analyst consensus changed" in result["reason"]

    def test_consensus_case_insensitive_no_recompute(self):
        result = should_recompute(_now(analyst="buy"), _prior(analyst_consensus="BUY"), today=TODAY)
        assert result["should_recompute"] is False

    def test_missing_consensus_on_either_side_does_not_trip(self):
        result = should_recompute(_now(analyst=None), _prior(analyst_consensus="BUY"), today=TODAY)
        assert result["should_recompute"] is False


class TestFundamentalsThresholds:
    def test_revenue_growth_move_above_threshold_forces_recompute(self):
        result = should_recompute(_now(revenue_growth=0.16), _prior(revenue_growth=0.10), today=TODAY)
        assert result["should_recompute"] is True
        assert "Revenue growth" in result["reason"]

    def test_revenue_growth_move_below_threshold_no_recompute(self):
        result = should_recompute(_now(revenue_growth=0.14), _prior(revenue_growth=0.10), today=TODAY)
        assert result["should_recompute"] is False

    def test_earnings_growth_move_above_threshold_forces_recompute(self):
        result = should_recompute(_now(earnings_growth=0.30), _prior(earnings_growth=0.15), today=TODAY)
        assert result["should_recompute"] is True

    def test_profit_margin_move_above_threshold_forces_recompute(self):
        result = should_recompute(_now(profit_margin=0.10), _prior(profit_margin=0.20), today=TODAY)
        assert result["should_recompute"] is True

    def test_pe_forward_relative_move_forces_recompute(self):
        result = should_recompute(_now(pe_forward=25.0), _prior(pe_forward=20.0), today=TODAY)
        assert result["should_recompute"] is True
        assert "Forward P/E" in result["reason"]

    def test_debt_to_equity_relative_move_forces_recompute(self):
        result = should_recompute(_now(debt_to_equity=65.0), _prior(debt_to_equity=50.0), today=TODAY)
        assert result["should_recompute"] is True

    def test_market_cap_relative_move_forces_recompute(self):
        result = should_recompute(_now(market_cap=1_300_000_000), _prior(market_cap=1_000_000_000), today=TODAY)
        assert result["should_recompute"] is True

    def test_null_fields_on_either_side_do_not_trip(self):
        result = should_recompute(
            _now(revenue_growth=None, earnings_growth=None, profit_margin=None, pe_forward=None, debt_to_equity=None, market_cap=None),
            _prior(),
            today=TODAY,
        )
        assert result["should_recompute"] is False

    def test_zero_prior_value_does_not_divide_by_zero(self):
        result = should_recompute(_now(debt_to_equity=10.0), _prior(debt_to_equity=0.0), today=TODAY)
        assert result["should_recompute"] is False


class TestMultipleReasonsCombine:
    def test_multiple_triggers_all_listed(self):
        result = should_recompute(
            _now(analyst="SELL", revenue_growth=0.20),
            _prior(analyst_consensus="BUY", revenue_growth=0.10),
            today=TODAY,
        )
        assert result["should_recompute"] is True
        assert "Analyst consensus changed" in result["reason"]
        assert "Revenue growth" in result["reason"]
