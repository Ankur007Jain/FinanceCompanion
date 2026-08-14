"""
Tests for _widen_with_important_days — the Verdict Agent's "recent history" context
used to be a plain last-5-calendar-entries window with no protection against an
important day (verdict reversal, major catalyst) silently falling out of it once a
few quiet days pushed it beyond the last 5. Reported by Ankur, 2026-08-13.
"""
from datetime import date, timedelta

from models import StockAnalysis
from services.nightly_runner import _widen_with_important_days


def _analysis(ticker, days_ago, verdict="HOLD", important=False, reason=None):
    return StockAnalysis(
        ticker=ticker,
        analysis_date=date.today() - timedelta(days=days_ago),
        verdict=verdict,
        current_price=100.0,
        is_important_day=important,
        importance_reason=reason,
    )


class TestWidenWithImportantDays:
    def test_important_day_outside_last_5_gets_pulled_in(self, db_session):
        rows = [
            _analysis("HIST1", 8, verdict="BUY", important=True, reason="Verdict reversal"),
            _analysis("HIST1", 4, verdict="HOLD"),
            _analysis("HIST1", 3, verdict="HOLD"),
            _analysis("HIST1", 2, verdict="HOLD"),
            _analysis("HIST1", 1, verdict="HOLD"),
            _analysis("HIST1", 0, verdict="HOLD"),
        ]
        db_session.add_all(rows)
        db_session.commit()

        recent_all = rows[1:][::-1]  # last 5, newest-first — matches the real query's shape
        widened = _widen_with_important_days(db_session, "HIST1", recent_all)

        dates_included = {r.analysis_date for r in widened}
        assert rows[0].analysis_date in dates_included
        assert len(widened) == 6

    def test_important_day_already_in_last_5_is_not_duplicated(self, db_session):
        rows = [
            _analysis("HIST2", 4, verdict="HOLD"),
            _analysis("HIST2", 3, verdict="BUY", important=True, reason="Breakout"),
            _analysis("HIST2", 2, verdict="HOLD"),
            _analysis("HIST2", 1, verdict="HOLD"),
            _analysis("HIST2", 0, verdict="HOLD"),
        ]
        db_session.add_all(rows)
        db_session.commit()

        recent_all = rows[::-1]
        widened = _widen_with_important_days(db_session, "HIST2", recent_all)

        assert len(widened) == 5

    def test_important_day_beyond_lookback_window_is_not_included(self, db_session):
        rows = [
            _analysis("HIST3", 45, verdict="BUY", important=True, reason="Old catalyst"),
            _analysis("HIST3", 4, verdict="HOLD"),
            _analysis("HIST3", 3, verdict="HOLD"),
            _analysis("HIST3", 2, verdict="HOLD"),
            _analysis("HIST3", 1, verdict="HOLD"),
            _analysis("HIST3", 0, verdict="HOLD"),
        ]
        db_session.add_all(rows)
        db_session.commit()

        recent_all = rows[1:][::-1]
        widened = _widen_with_important_days(db_session, "HIST3", recent_all, lookback_days=30)

        assert len(widened) == 5

    def test_no_important_days_outside_window_returns_last_5_unchanged(self, db_session):
        rows = [_analysis("HIST4", d, verdict="HOLD") for d in range(4, -1, -1)]
        db_session.add_all(rows)
        db_session.commit()

        recent_all = rows[::-1]
        widened = _widen_with_important_days(db_session, "HIST4", recent_all)

        assert widened == recent_all

    def test_empty_recent_all_returns_empty(self, db_session):
        assert _widen_with_important_days(db_session, "HIST5", []) == []
