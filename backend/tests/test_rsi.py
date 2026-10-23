"""
Nightly RSI moved from simple 14-day rolling means (Cutler) to standard Wilder RSI on
2026-10-23 — the definition pandas_ta, price_agent.py and brokers use. The old one ran up to
~10pt off what users see elsewhere and flagged oversold/overbought ~3x as often (#156).
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from indicators import wilder_rsi  # noqa: E402
import backfill_rsi_wilder as backfill  # noqa: E402


def _walk(n=300, seed=7):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2026-01-02", periods=n).date
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, n))), index=days)


class TestWilderRSI:
    def test_matches_pandas_ta(self):
        ta = pytest.importorskip("pandas_ta")
        close = _walk()
        ours, theirs = wilder_rsi(close), ta.rsi(close, length=14)
        both = pd.concat([ours, theirs], axis=1).dropna()
        assert len(both) > 250
        assert (both.iloc[:, 0] - both.iloc[:, 1]).abs().max() < 1e-9

    def test_edges(self):
        rising = pd.Series(np.arange(1.0, 40.0))
        flat = pd.Series([50.0] * 40)
        assert wilder_rsi(rising).iloc[-1] == pytest.approx(100.0)
        assert wilder_rsi(flat).iloc[-1] == 50.0

    def test_is_smoother_than_the_old_simple_average(self):
        close = _walk()
        old, new = backfill.cutler_rsi(close).dropna(), wilder_rsi(close).iloc[30:]
        assert ((new < 30) | (new > 70)).sum() < ((old < 30) | (old > 70)).sum()

    def test_nightly_fetch_uses_it(self):
        src = (SCRIPTS / "nightly_fetch.py").read_text()
        assert 'rsi   = float(wilder_rsi(hist["Close"]).iloc[-1])' in src
        assert "rolling(14)" not in src


class TestCorrectedRSI:
    def setup_method(self):
        self.close = _walk()
        self.old, self.new = backfill.cutler_rsi(self.close), wilder_rsi(self.close)
        self.days = list(self.close.index)

    def test_rewrites_when_the_old_value_reproduces_from_the_prior_bar(self):
        run_day, bar = self.days[200], self.days[199]
        status, value = backfill.corrected_rsi(round(float(self.old[bar]), 1), run_day, self.old, self.new)
        assert (status, value) == ("fix", round(float(self.new[bar]), 1))

    def test_falls_back_to_the_same_day_bar_for_retry_runs(self):
        run_day = self.days[200]
        status, value = backfill.corrected_rsi(round(float(self.old[run_day]), 1), run_day, self.old, self.new)
        assert (status, value) == ("fix", round(float(self.new[run_day]), 1))

    def test_leaves_rows_it_cannot_reproduce(self):
        assert backfill.corrected_rsi(12.3, self.days[200], self.old, self.new) == ("no_match", None)
        assert backfill.corrected_rsi(50.0, self.days[0] - timedelta(days=5), self.old, self.new) == ("no_prices", None)


def test_run_dry_run_then_apply(tmp_path):
    from models import Base, PriceHistory, StockAnalysis
    engine = create_engine(f"sqlite:///{tmp_path / 'rsi.db'}")
    Base.metadata.create_all(engine)
    close = _walk()
    old = backfill.cutler_rsi(close)
    days = list(close.index)
    with sessionmaker(bind=engine)() as s:
        s.add_all(PriceHistory(symbol="RSIX", date=d, close=float(c)) for d, c in close.items())
        good = StockAnalysis(ticker="RSIX", analysis_date=days[-1], verdict="WATCH", rsi=round(float(old[days[-2]]), 1))
        odd = StockAnalysis(ticker="RSIX", analysis_date=days[-2], verdict="WATCH", rsi=12.3)
        s.add_all([good, odd])
        s.commit()
        good_id, odd_id = good.id, odd.id
    since = (days[-1] - timedelta(days=10)).isoformat()

    summary, fixes = backfill.run(engine, apply=False, since=since)
    assert (summary["to_fix"], summary["skipped_no_match"]) == (1, 1)
    with sessionmaker(bind=engine)() as s:
        assert s.get(StockAnalysis, good_id).rsi == round(float(old[days[-2]]), 1)  # dry run wrote nothing

    backup = tmp_path / "old_rsi.json"
    backfill.run(engine, apply=True, backup=str(backup), since=since)
    with sessionmaker(bind=engine)() as s:
        assert s.get(StockAnalysis, good_id).rsi == pytest.approx(round(float(wilder_rsi(close)[days[-2]]), 1))
        assert s.get(StockAnalysis, odd_id).rsi == 12.3
    assert json.loads(backup.read_text())[0]["old_rsi"] == fixes[0]["old_rsi"]
