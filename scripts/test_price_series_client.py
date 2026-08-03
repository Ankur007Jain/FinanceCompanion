"""
Unit + parity tests for price_series_client.fetch_series — the piece of the
redundant-refetch fix that actually touches nightly_fetch.py's computation path.

Not part of `backend/tests/` (that suite is FastAPI/DB-only) — run with
`pytest scripts/test_price_series_client.py` from the repo root. Needs pandas/requests,
already present in the backend venv.
"""
import pandas as pd
import pytest

from price_series_client import fetch_series


class _FakeResponse:
    def __init__(self, bars):
        self._bars = bars

    def raise_for_status(self):
        pass

    def json(self):
        return {"bars": self._bars}


# The same underlying OHLCV values, in yfinance's native shape (DatetimeIndex named
# "Date") vs the JSON-bars shape our backend endpoint returns them in. 20 rows so RSI's
# 14-period rolling window actually produces a real number on both paths, not NaN==NaN.
_RAW_ROWS = [
    {"Date": f"2026-05-{d:02d}", "Open": o, "High": o + 2.5, "Low": o - 1.0, "Close": c, "Volume": 40_000_000 + d * 100_000}
    for d, (o, c) in enumerate([
        (100.0, 101.2), (101.2, 102.0), (102.0, 101.5), (101.5, 103.1), (103.1, 104.0),
        (104.0, 103.4), (103.4, 105.2), (105.2, 106.0), (106.0, 105.1), (105.1, 107.3),
        (107.3, 108.0), (108.0, 107.2), (107.2, 109.5), (109.5, 110.1), (110.1, 109.8),
        (109.8, 111.0), (111.0, 112.4), (112.4, 111.9), (111.9, 113.5), (113.5, 114.2),
    ], start=1)
]


def _yfinance_shaped_df() -> pd.DataFrame:
    df = pd.DataFrame(_RAW_ROWS)
    df.index = pd.to_datetime(df.pop("Date"))
    df.index.name = "Date"
    return df


def _fetch_series_via_backend(monkeypatch) -> pd.DataFrame:
    bars = [
        {"date": r["Date"], "open": r["Open"], "high": r["High"], "low": r["Low"],
         "close": r["Close"], "volume": r["Volume"]}
        for r in _RAW_ROWS
    ]
    monkeypatch.setattr("price_series_client.requests.post", lambda *a, **k: _FakeResponse(bars))
    return fetch_series("NVDA", "http://backend", "secret")


# Same formulas nightly_fetch.py applies to `hist` — duplicated here (not imported,
# nightly_fetch.py is a top-level script, not an importable module) so this test can
# assert both DataFrame shapes really do produce identical downstream numbers, not just
# that they look superficially similar.
def _ma(hist, window):
    return float(hist["Close"].rolling(window).mean().iloc[-1]) if len(hist) >= window else None


def _rsi(hist):
    delta = hist["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    return float(100 - 100 / (1 + gain.iloc[-1] / loss.iloc[-1])) if loss.iloc[-1] != 0 else 50


def _pivot(hist):
    prev_h, prev_l, prev_c = float(hist["High"].iloc[-2]), float(hist["Low"].iloc[-2]), float(hist["Close"].iloc[-2])
    pivot = round((prev_h + prev_l + prev_c) / 3, 2)
    return pivot, round(2 * pivot - prev_l, 2), round(2 * pivot - prev_h, 2)


class TestFetchSeriesShape:
    def test_columns_match_yfinance_convention(self, monkeypatch):
        hist = _fetch_series_via_backend(monkeypatch)
        assert list(hist.columns) == ["Open", "High", "Low", "Close", "Volume"]

    def test_index_name_is_date_matching_yfinance(self, monkeypatch):
        """nightly_fetch.py's raw-snapshot serializer does hist.reset_index() then reads
        hist_r["Date"] — a mismatched index name here silently drops history_json to "[]"."""
        hist = _fetch_series_via_backend(monkeypatch)
        assert hist.index.name == "Date"
        assert "Date" in hist.reset_index().columns

    def test_chronological_order_preserved(self, monkeypatch):
        hist = _fetch_series_via_backend(monkeypatch)
        assert list(hist.index) == sorted(hist.index)

    def test_empty_bars_returns_empty_dataframe(self, monkeypatch):
        monkeypatch.setattr("price_series_client.requests.post", lambda *a, **k: _FakeResponse([]))
        hist = fetch_series("NEWTICK", "http://backend", "secret")
        assert hist.empty


class TestParityWithOldYfinanceShapedPath:
    """The regression check: same underlying values, computed two ways, must match —
    proving the switch from a fresh yfinance pull to the price_history-backed fetch
    didn't change any of the numbers nightly_fetch.py reports."""

    def test_moving_averages_match(self, monkeypatch):
        old, new = _yfinance_shaped_df(), _fetch_series_via_backend(monkeypatch)
        assert _ma(old, 2) == _ma(new, 2)

    def test_rsi_matches(self, monkeypatch):
        old, new = _yfinance_shaped_df(), _fetch_series_via_backend(monkeypatch)
        assert _rsi(old) == pytest.approx(_rsi(new))

    def test_pivot_points_match(self, monkeypatch):
        old, new = _yfinance_shaped_df(), _fetch_series_via_backend(monkeypatch)
        assert _pivot(old) == _pivot(new)

    def test_support_resistance_match(self, monkeypatch):
        old, new = _yfinance_shaped_df(), _fetch_series_via_backend(monkeypatch)
        assert round(float(old["Close"].tail(20).min()), 2) == round(float(new["Close"].tail(20).min()), 2)
        assert round(float(old["Close"].tail(20).max()), 2) == round(float(new["Close"].tail(20).max()), 2)
