"""
Tests for the ticker correlation matrix's statistical math (scripts/compute_correlations.py).
Synthetic price series, no network — verifies the compute logic the correlation job trusts.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from compute_correlations import (  # noqa: E402
    log_returns, residualize, pairwise_correlation, benjamini_hochberg, compute_correlation_matrix,
)


def _dates(n: int, start: date = date(2026, 1, 1)) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _series(prices: list[float], start: date = date(2026, 1, 1)) -> dict[str, float]:
    return dict(zip(_dates(len(prices), start), prices))


class TestLogReturns:
    def test_drops_first_date_no_prior_close(self):
        closes = _series([100.0, 101.0, 99.0])
        returns = log_returns(closes)
        assert len(returns) == 2

    def test_flat_price_gives_zero_return(self):
        closes = _series([100.0, 100.0, 100.0])
        returns = log_returns(closes)
        assert all(abs(r) < 1e-9 for r in returns.values())

    def test_gain_gives_positive_return(self):
        closes = _series([100.0, 110.0])
        returns = log_returns(closes)
        assert list(returns.values())[0] > 0


class TestResidualize:
    def test_below_min_overlap_returns_empty(self):
        ticker = _series([100 + i for i in range(10)])
        market = _series([1000 + i for i in range(10)])
        assert residualize(log_returns(ticker), log_returns(market)) == {}

    def test_perfect_market_tracker_has_near_zero_residuals(self):
        rng = np.random.default_rng(42)
        market_prices = [1000.0]
        for _ in range(99):
            market_prices.append(market_prices[-1] * (1 + rng.normal(0, 0.01)))
        # ticker moves exactly 1.5x the market every day — pure beta, no idiosyncratic move
        market_ret = log_returns(_series(market_prices))
        ticker_prices = [100.0]
        dates = sorted(market_ret.keys())
        for d in dates:
            ticker_prices.append(ticker_prices[-1] * np.exp(1.5 * market_ret[d]))
        ticker = _series(ticker_prices)
        resid = residualize(log_returns(ticker), market_ret)
        assert resid  # enough overlap
        assert max(abs(v) for v in resid.values()) < 1e-6


class TestPairwiseCorrelation:
    def test_insufficient_overlap_returns_none(self):
        a = {d: 0.01 for d in _dates(10)}
        b = {d: 0.01 for d in _dates(10)}
        assert pairwise_correlation(a, b, window=90, min_overlap=20) is None

    def test_identical_series_correlate_perfectly(self):
        rng = np.random.default_rng(1)
        vals = rng.normal(0, 0.02, 40)
        a = dict(zip(_dates(40), vals))
        b = dict(a)
        result = pairwise_correlation(a, b, window=30, min_overlap=20)
        assert result is not None
        r, p, n = result
        assert r > 0.999
        assert p < 0.01

    def test_zero_variance_series_returns_none(self):
        a = {d: 0.0 for d in _dates(30)}
        b = {d: 0.01 for d in _dates(30)}
        assert pairwise_correlation(a, b, window=30, min_overlap=20) is None

    def test_uncorrelated_random_series_low_r_high_p(self):
        rng = np.random.default_rng(7)
        a = dict(zip(_dates(60), rng.normal(0, 0.02, 60)))
        b = dict(zip(_dates(60), rng.normal(0, 0.02, 60)))
        result = pairwise_correlation(a, b, window=60, min_overlap=20)
        assert result is not None
        r, p, n = result
        assert abs(r) < 0.5  # not a guaranteed bound, but true for this fixed seed
        assert n == 60


class TestBenjaminiHochberg:
    def test_empty_input(self):
        assert benjamini_hochberg([]) == []

    def test_all_p_values_tiny_all_survive(self):
        p_values = [0.0001, 0.0002, 0.0003, 0.0004]
        assert all(benjamini_hochberg(p_values))

    def test_all_p_values_large_none_survive(self):
        p_values = [0.8, 0.9, 0.7, 0.95]
        assert not any(benjamini_hochberg(p_values))

    def test_mixed_p_values_fewer_survive_than_uncorrected_threshold(self):
        # 2 genuinely tiny p-values, a batch of borderline ones, and a batch clearly
        # above alpha. Uncorrected (p<0.05), the tiny AND borderline values would all
        # "pass" — FDR correction should reject the borderline batch too, since BH's
        # step-up procedure only accepts a rank if its p-value clears (rank/n)*alpha,
        # and the batch above alpha breaks the cascade that would otherwise let
        # borderline values ride through at the highest ranks.
        p_values = [0.001, 0.002] + [0.04] * 5 + [0.5] * 15
        survives = benjamini_hochberg(p_values)
        assert survives[0] and survives[1]  # the genuinely tiny ones survive
        assert not any(survives[2:7])  # the borderline batch does not survive
        assert not any(survives[7:])  # the clearly-insignificant batch does not survive


class TestComputeCorrelationMatrix:
    def test_two_tickers_alphabetized_pair(self):
        rng = np.random.default_rng(3)
        market = {d: 1000 + i for i, d in enumerate(_dates(100))}
        market_series = {}
        price = 1000.0
        for d in _dates(100):
            price *= (1 + rng.normal(0, 0.01))
            market_series[d] = price
        closes = {
            "ZBRAVO": {d: 100 * (1 + 0.001 * i) for i, d in enumerate(_dates(100))},
            "ZALPHA": {d: 50 * (1 + 0.001 * i) for i, d in enumerate(_dates(100))},
        }
        pairs = compute_correlation_matrix(closes, market_series, windows=(30, 90), min_overlap=20)
        assert len(pairs) == 1
        assert pairs[0]["ticker_a"] == "ZALPHA"
        assert pairs[0]["ticker_b"] == "ZBRAVO"

    def test_ticker_with_insufficient_history_excluded(self):
        market_series = {d: 1000 + i for i, d in enumerate(_dates(100))}
        closes = {
            "ZGOOD": {d: 100 + i for i, d in enumerate(_dates(100))},
            "ZTHIN": {d: 50 + i for i, d in enumerate(_dates(5))},  # way below min overlap
        }
        pairs = compute_correlation_matrix(closes, market_series)
        assert pairs == []

    def test_significant_field_always_present(self):
        market_series = {d: 1000 + i for i, d in enumerate(_dates(100))}
        closes = {
            "ZONE": {d: 100 + i * 0.5 for i, d in enumerate(_dates(100))},
            "ZTWO": {d: 50 - i * 0.3 for i, d in enumerate(_dates(100))},
        }
        pairs = compute_correlation_matrix(closes, market_series)
        assert len(pairs) == 1
        assert "significant" in pairs[0]
        assert isinstance(pairs[0]["significant"], bool)
