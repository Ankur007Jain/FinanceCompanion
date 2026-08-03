"""
Unit tests for services.price_history_sync.

Regression coverage for the redundant-refetch fix: nightly_fetch.py used to re-pull a
full 5-year yfinance history every run, for every ticker, plus separately for "^GSPC"
and the sector ETF on every single ticker that referenced them. This module backfills
each symbol once, then only appends new bars — these tests cover that branching logic
directly, including a bug caught during implementation (the monthly dividend-drift
refresh firing on every call within days 1-3 of the month, not just the first sync of
that day, which would have defeated caching for shared symbols like SPY/sector ETFs).

`_backfill`/`_incremental` are the only network-touching functions in this module — they
're monkeypatched in the orchestration tests below so `sync_and_get_bars`'s branching can
be tested without hitting yfinance, same spirit as this repo's existing tests (feed
realistic fixtures into logic, don't hit the network) but adapted since this module's
core logic is inherently coupled to network calls in a way _extract_cashflow's is not.
"""
from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy.exc import IntegrityError

from models import PriceHistory
from services import price_history_sync as phs


def _hist_df(rows: list[dict]) -> pd.DataFrame:
    """Builds a DataFrame shaped like yfinance's history() output: DatetimeIndex named
    Date, OHLCV + Stock Splits columns."""
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df.pop("Date"))
    return df


class TestRowsFromHistory:
    def test_empty_dataframe_returns_no_rows(self):
        assert phs._rows_from_history("AAPL", pd.DataFrame()) == []

    def test_extracts_ohlcv_and_defaults_missing_split_to_zero(self):
        df = _hist_df([{"Date": "2026-06-01", "Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 1000}])
        rows = phs._rows_from_history("AAPL", df)
        assert rows == [{
            "symbol": "AAPL", "date": date(2026, 6, 1),
            "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1000,
            "stock_split": 0.0,
        }]

    def test_nonzero_stock_split_is_carried_through(self):
        df = _hist_df([{"Date": "2026-06-01", "Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5,
                         "Volume": 1000, "Stock Splits": 4.0}])
        rows = phs._rows_from_history("NVDA", df)
        assert rows[0]["stock_split"] == 4.0


class TestSyncAndGetBars:
    def _seed(self, db_session, symbol: str, d: date, close: float = 100.0):
        db_session.merge(PriceHistory(symbol=symbol, date=d, open=close, high=close, low=close,
                                       close=close, volume=1, stock_split=0.0))
        db_session.commit()

    def test_new_symbol_triggers_backfill_not_incremental(self, db_session, monkeypatch):
        calls = []
        monkeypatch.setattr(phs, "_backfill", lambda db, symbol, overwrite=False: calls.append(("backfill", overwrite)))
        monkeypatch.setattr(phs, "_incremental", lambda db, symbol, since: pytest.fail("should not be called"))

        phs.sync_and_get_bars("NEWTICK", db_session)

        assert calls == [("backfill", False)]

    def test_already_synced_today_is_a_pure_cache_hit(self, db_session, monkeypatch):
        """The case that actually collapses repeated ^GSPC/sector-ETF fetches across every
        ticker in a batch to one — if this fires _backfill or _incremental, caching is broken."""
        self._seed(db_session, "^GSPC", date.today())
        monkeypatch.setattr(phs, "_backfill", lambda *a, **k: pytest.fail("must not refetch — already synced today"))
        monkeypatch.setattr(phs, "_incremental", lambda *a, **k: pytest.fail("must not refetch — already synced today"))

        bars = phs.sync_and_get_bars("^GSPC", db_session)

        assert len(bars) == 1

    def test_stale_data_triggers_incremental_since_day_after_last_sync(self, db_session, monkeypatch):
        # Frozen outside the day<=3 monthly-refresh window (see tests below) so this is
        # deterministic regardless of what day it's actually run on.
        monkeypatch.setattr(phs, "date", _FixedDate)
        _FixedDate._today = date(2026, 8, 15)
        yesterday = _FixedDate._today - timedelta(days=1)
        self._seed(db_session, "MSFT", yesterday)
        calls = []
        monkeypatch.setattr(phs, "_incremental", lambda db, symbol, since: calls.append(since) or False)
        monkeypatch.setattr(phs, "_backfill", lambda *a, **k: pytest.fail("should not fully backfill on a plain gap"))

        phs.sync_and_get_bars("MSFT", db_session)

        assert calls == [yesterday + timedelta(days=1)]

    def test_split_detected_in_incremental_forces_full_backfill(self, db_session, monkeypatch):
        self._seed(db_session, "NVDA", date.today() - timedelta(days=1))
        monkeypatch.setattr(phs, "_incremental", lambda db, symbol, since: True)  # split detected
        backfill_calls = []
        monkeypatch.setattr(phs, "_backfill", lambda db, symbol, overwrite=False: backfill_calls.append(overwrite))

        phs.sync_and_get_bars("NVDA", db_session)

        assert backfill_calls == [True]

    def test_monthly_refresh_fires_on_day_transition_within_first_3_days(self, db_session, monkeypatch):
        """Regression for the bug caught during implementation: this must trigger from the
        latest<today branch (a real day transition), not from a separate 'already synced
        today AND day<=3' check — otherwise a second ticker sharing this symbol later the
        same day would force another full backfill instead of getting a cache hit."""
        monkeypatch.setattr(phs, "date", _FixedDate)
        _FixedDate._today = date(2026, 8, 1)
        self._seed(db_session, "XLK", date(2026, 7, 31))
        backfill_calls = []
        monkeypatch.setattr(phs, "_backfill", lambda db, symbol, overwrite=False: backfill_calls.append(overwrite))
        monkeypatch.setattr(phs, "_incremental", lambda *a, **k: pytest.fail("day<=3 transition should force-backfill, not increment"))

        phs.sync_and_get_bars("XLK", db_session)

        assert backfill_calls == [True]

    def test_no_monthly_refetch_for_a_second_ticker_later_the_same_day(self, db_session, monkeypatch):
        """The actual bug: after the first sync of a day<=3 has already happened, a second
        ticker asking for the same shared symbol must be a pure cache hit, not another backfill."""
        monkeypatch.setattr(phs, "date", _FixedDate)
        _FixedDate._today = date(2026, 8, 1)
        self._seed(db_session, "XLK", date(2026, 8, 1))  # already synced today
        monkeypatch.setattr(phs, "_backfill", lambda *a, **k: pytest.fail("already synced today — must be a cache hit"))
        monkeypatch.setattr(phs, "_incremental", lambda *a, **k: pytest.fail("already synced today — must be a cache hit"))

        phs.sync_and_get_bars("XLK", db_session)


class TestWriteRowsConcurrency:
    def test_integrity_error_on_commit_is_swallowed_not_raised(self, db_session, monkeypatch):
        """Up to 6 nightly batches run concurrently (.github/workflows/nightly.yml,
        max-parallel: 6) and race to write the same shared symbol — most acutely on the
        very first backfill night, when every batch's first ticker in a sector/index
        tries to seed it simultaneously. A duplicate-PK IntegrityError from a concurrent
        writer must not crash this ticker's analysis; sync_and_get_bars re-reads fresh
        state afterward regardless of which writer's commit actually won."""
        monkeypatch.setattr(db_session, "commit", lambda: (_ for _ in ()).throw(
            IntegrityError("INSERT INTO price_history ...", {}, Exception("duplicate key"))
        ))
        rollback_calls = []
        monkeypatch.setattr(db_session, "rollback", lambda: rollback_calls.append(True))

        phs._write_rows(db_session, "AAPL", [{
            "symbol": "AAPL", "date": date(2026, 6, 1), "open": 1.0, "high": 1.0,
            "low": 1.0, "close": 1.0, "volume": 1, "stock_split": 0.0,
        }])  # must not raise

        assert rollback_calls == [True]


class _FixedDate(date):
    _today = date(2026, 1, 1)

    @classmethod
    def today(cls):
        return cls._today
