"""
Tests for the self-derived fundamentals trend (scripts/compute_fundamentals_trend.py).
Pure function, no I/O.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from compute_fundamentals_trend import compute_trend  # noqa: E402


def _history(**series):
    """series: field_name -> list of (date_str, value) tuples."""
    history: dict = {}
    for field, points in series.items():
        for d, v in points:
            history.setdefault(d, {})[field] = v
    return history


class TestInsufficientData:
    def test_empty_history_returns_all_none(self):
        result = compute_trend({})
        assert all(v is None for v in result.values())

    def test_single_data_point_returns_none_for_that_field(self):
        history = _history(revenue_growth=[("2026-01-01", 0.10)])
        result = compute_trend(history)
        assert result["revenue_growth_trend"] is None

    def test_all_null_values_returns_none(self):
        history = {"2026-01-01": {"revenue_growth": None}, "2026-02-01": {"revenue_growth": None}}
        result = compute_trend(history)
        assert result["revenue_growth_trend"] is None


class TestRevenueGrowthTrend:
    def test_accelerating_above_threshold(self):
        history = _history(revenue_growth=[("2026-01-01", 0.10), ("2026-06-01", 0.16)])
        result = compute_trend(history)
        assert result["revenue_growth_trend"] == "ACCELERATING"

    def test_decelerating_below_threshold(self):
        history = _history(revenue_growth=[("2026-01-01", 0.40), ("2026-06-01", 0.15)])
        result = compute_trend(history)
        assert result["revenue_growth_trend"] == "DECELERATING"

    def test_stable_within_threshold(self):
        history = _history(revenue_growth=[("2026-01-01", 0.10), ("2026-06-01", 0.11)])
        result = compute_trend(history)
        assert result["revenue_growth_trend"] == "STABLE"

    def test_uses_earliest_and_latest_not_min_max(self):
        # Latest (0.12) is close to earliest (0.10) even though it spiked to 0.30 mid-window.
        history = _history(revenue_growth=[
            ("2026-01-01", 0.10), ("2026-03-01", 0.30), ("2026-06-01", 0.12),
        ])
        result = compute_trend(history)
        assert result["revenue_growth_trend"] == "STABLE"

    def test_unsorted_input_still_uses_correct_endpoints(self):
        history = _history(revenue_growth=[("2026-06-01", 0.16), ("2026-01-01", 0.10)])
        result = compute_trend(history)
        assert result["revenue_growth_trend"] == "ACCELERATING"


class TestMarginTrend:
    def test_expanding_margin(self):
        history = _history(profit_margin=[("2026-01-01", 0.15), ("2026-06-01", 0.19)])
        result = compute_trend(history)
        assert result["margin_trend_recent"] == "EXPANDING"

    def test_contracting_margin(self):
        history = _history(profit_margin=[("2026-01-01", 0.20), ("2026-06-01", 0.15)])
        result = compute_trend(history)
        assert result["margin_trend_recent"] == "CONTRACTING"


class TestOwnershipTrends:
    def test_institutions_accumulating(self):
        history = _history(inst_ownership_pct=[("2026-01-01", 0.50), ("2026-06-01", 0.53)])
        result = compute_trend(history)
        assert result["inst_ownership_trend"] == "ACCUMULATING"

    def test_institutions_distributing(self):
        history = _history(inst_ownership_pct=[("2026-01-01", 0.60), ("2026-06-01", 0.55)])
        result = compute_trend(history)
        assert result["inst_ownership_trend"] == "DISTRIBUTING"

    def test_insiders_increasing(self):
        history = _history(insider_ownership_pct=[("2026-01-01", 0.10), ("2026-06-01", 0.13)])
        result = compute_trend(history)
        assert result["insider_ownership_trend"] == "INCREASING"

    def test_insiders_decreasing(self):
        history = _history(insider_ownership_pct=[("2026-01-01", 0.15), ("2026-06-01", 0.11)])
        result = compute_trend(history)
        assert result["insider_ownership_trend"] == "DECREASING"


class TestFieldsAreIndependent:
    def test_mixed_availability_only_scores_available_fields(self):
        history = _history(
            revenue_growth=[("2026-01-01", 0.10), ("2026-06-01", 0.20)],
            profit_margin=[("2026-06-01", 0.15)],  # only one point — insufficient
        )
        result = compute_trend(history)
        assert result["revenue_growth_trend"] == "ACCELERATING"
        assert result["margin_trend_recent"] is None
        assert result["inst_ownership_trend"] is None
