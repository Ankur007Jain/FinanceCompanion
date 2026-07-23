"""
Tests for services/nightly_runner.py's cost-tracking helper — two real bugs found
while auditing token usage this session:
1. claude-haiku-4-5-20251001's rates were stale ($0.80/$4.00/$0.08 vs the real
   published $1/$5/$0.10) — understated Haiku cost by 20% in every cost_usd figure.
2. cache_write tokens were tracked in the returned tuple but never priced into
   `cost` at all — every cache write this app has paid for was invisible to cost_usd.
"""
from services.nightly_runner import _PRICING, _sum_usages


def _usage(model, input_tokens=0, output_tokens=0, cache_read=0, cache_write=0):
    return {
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "cache_read": cache_read, "cache_write": cache_write, "model": model,
    }


class TestSumUsages:
    def test_sonnet_5_priced_correctly(self):
        tin, tout, tcr, tcw, cost = _sum_usages([
            _usage("claude-sonnet-5", input_tokens=1_000_000, output_tokens=1_000_000),
        ])
        assert cost == 2.0 + 10.0  # $2 in + $10 out per the real published rate

    def test_haiku_priced_correctly_not_the_old_stale_rate(self):
        """Real bug: this used to compute 0.80 + 4.0 = 4.80, understating the real
        published rate ($1 in / $5 out per MTok) by 20%."""
        tin, tout, tcr, tcw, cost = _sum_usages([
            _usage("claude-haiku-4-5-20251001", input_tokens=1_000_000, output_tokens=1_000_000),
        ])
        assert cost == 1.0 + 5.0

    def test_cache_write_tokens_are_actually_priced(self):
        """Real bug: cache_write was summed into the returned tuple but never
        included in the cost calculation at all — this used to return cost=0.0."""
        tin, tout, tcr, tcw, cost = _sum_usages([
            _usage("claude-sonnet-5", cache_write=1_000_000),
        ])
        assert tcw == 1_000_000
        assert cost == 2.50  # sonnet-5's 5m cache-write rate

    def test_cache_read_still_priced(self):
        tin, tout, tcr, tcw, cost = _sum_usages([
            _usage("claude-sonnet-5", cache_read=1_000_000),
        ])
        assert cost == 0.20

    def test_unknown_model_falls_back_to_sonnet_5_default(self):
        tin, tout, tcr, tcw, cost = _sum_usages([
            _usage("some-unrecognized-model", input_tokens=1_000_000),
        ])
        assert cost == _PRICING["claude-sonnet-5"]["in"]

    def test_sums_across_multiple_usages_and_models(self):
        tin, tout, tcr, tcw, cost = _sum_usages([
            _usage("claude-sonnet-5", input_tokens=500_000),
            _usage("claude-haiku-4-5-20251001", output_tokens=200_000),
        ])
        assert tin == 500_000
        assert tout == 200_000
        assert cost == pytest_approx_sum(500_000 / 1_000_000 * 2.0, 200_000 / 1_000_000 * 5.0)

    def test_empty_list_returns_zeros(self):
        assert _sum_usages([]) == (0, 0, 0, 0, 0.0)


def pytest_approx_sum(*parts):
    return round(sum(parts), 6)
