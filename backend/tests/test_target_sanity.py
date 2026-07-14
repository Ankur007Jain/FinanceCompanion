"""Tests for _check_target_sanity — the hallucination bounds-check on nightly ingest."""
from routers.jobs import _check_target_sanity


class TestBuyVerdict:
    def test_stop_at_or_above_current_price_flagged(self):
        issues = _check_target_sanity("BUY", 100.0, entry_target=95.0, exit_target=110.0, stop_loss=101.0)
        assert any("stop_loss" in i for i in issues)

    def test_exit_not_above_entry_flagged(self):
        issues = _check_target_sanity("BUY", 100.0, entry_target=100.0, exit_target=98.0, stop_loss=90.0)
        assert any("exit_target" in i for i in issues)

    def test_entry_far_from_current_price_flagged(self):
        issues = _check_target_sanity("BUY", 100.0, entry_target=150.0, exit_target=160.0, stop_loss=90.0)
        assert any("entry_target" in i for i in issues)

    def test_clean_buy_has_no_issues(self):
        issues = _check_target_sanity("BUY", 100.0, entry_target=99.0, exit_target=110.0, stop_loss=94.0)
        assert issues == []


class TestSellVerdict:
    def test_stop_at_or_below_current_price_flagged(self):
        issues = _check_target_sanity("SELL", 100.0, entry_target=101.0, exit_target=90.0, stop_loss=99.0)
        assert any("stop_loss" in i for i in issues)

    def test_exit_not_below_entry_flagged(self):
        issues = _check_target_sanity("SELL", 100.0, entry_target=100.0, exit_target=105.0, stop_loss=110.0)
        assert any("exit_target" in i for i in issues)

    def test_clean_sell_has_no_issues(self):
        issues = _check_target_sanity("SELL", 100.0, entry_target=101.0, exit_target=90.0, stop_loss=106.0)
        assert issues == []


class TestNonDirectionalVerdicts:
    def test_hold_never_flagged(self):
        assert _check_target_sanity("HOLD", 100.0, entry_target=200.0, exit_target=50.0, stop_loss=150.0) == []

    def test_watch_never_flagged(self):
        assert _check_target_sanity("WATCH", 100.0, entry_target=200.0, exit_target=50.0, stop_loss=150.0) == []


class TestMissingData:
    def test_no_current_price_returns_empty(self):
        assert _check_target_sanity("BUY", None, entry_target=95.0, exit_target=110.0, stop_loss=90.0) == []

    def test_none_targets_dont_crash(self):
        issues = _check_target_sanity("BUY", 100.0, entry_target=None, exit_target=None, stop_loss=None)
        assert issues == []
