"""
Day-change bug (found via issue #152): nightly_fetch.py read yfinance fast_info.previous_close,
unreliable in the pre-market window most runs land in — 64% of rows since 2026-09-01 had the
wrong daily move. Fixture values are the real STX snapshots from those nights.
"""
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from quote_fields import regular_session_quote  # noqa: E402
from backfill_day_change import corrected_fields, run  # noqa: E402

STX_OCT14 = {"currentPrice": 713.54, "regularMarketPrice": 713.54, "previousClose": 747.2, "regularMarketPreviousClose": 747.2}


class TestRegularSessionQuote:
    def test_real_stx_snapshot_gives_the_real_move(self):
        price, prev, chg = regular_session_quote(STX_OCT14)
        assert (price, prev) == (713.54, 747.2)
        assert round(chg, 2) == -4.50

    def test_missing_previous_close_is_none_not_a_fake_flat_day(self):
        price, prev, chg = regular_session_quote({"regularMarketPrice": 100.0})
        assert price == 100.0 and prev is None and chg is None

    def test_falls_back_to_previousClose_and_fallback_price(self):
        _, _, chg = regular_session_quote({"previousClose": 50.0}, fallback_price=55.0)
        assert round(chg, 2) == 10.0

    def test_garbage_values_are_rejected(self):
        assert regular_session_quote({"regularMarketPrice": "n/a", "previousClose": 0})[2] is None
        assert regular_session_quote(None)[2] is None


class TestCorrectedFields:
    def test_fixes_the_stx_row(self):
        status, chg, rel = corrected_fields(713.54, 3.35, -2.98, 6.33, STX_OCT14)
        assert status == "fix"
        assert chg == -4.5
        assert rel == -1.52  # -4.50 - (-2.98)

    def test_zero_row_gets_fixed(self):
        info = {"regularMarketPrice": 753.25, "regularMarketPreviousClose": 783.0}
        status, chg, _ = corrected_fields(753.25, 0.0, -1.22, 1.22, info)
        assert (status, chg) == ("fix", -3.8)

    def test_correct_row_is_left_alone(self):
        assert corrected_fields(713.54, -4.5, -2.98, -1.52, STX_OCT14)[0] == "ok"

    def test_snapshot_from_a_different_quote_is_not_trusted(self):
        assert corrected_fields(800.0, 0.0, None, None, STX_OCT14)[0] == "different_quote"

    def test_no_snapshot_quote(self):
        assert corrected_fields(713.54, 3.35, None, None, {})[0] == "no_quote"

    def test_penny_stock_uses_unrounded_snapshot_price(self):
        # Real BLNK 2026-10-20 row: stored price rounded to 0.42; true move 0.4211/0.4235 = -0.57%.
        info = {"regularMarketPrice": 0.4211, "regularMarketPreviousClose": 0.4235}
        assert corrected_fields(0.42, -0.57, -0.64, 0.07, info) == ("ok", -0.57, 0.07)

    def test_nan_relative_strength_is_cleared_once_then_ok(self):
        nan = float("nan")
        status, chg, rel = corrected_fields(713.54, -4.5, nan, nan, STX_OCT14)
        assert (status, chg, rel) == ("fix", -4.5, None)
        assert corrected_fields(713.54, -4.5, nan, None, STX_OCT14)[0] == "ok"

    def test_missing_sector_keeps_existing_relative_strength(self):
        _, _, rel = corrected_fields(713.54, 3.35, None, 9.9, STX_OCT14)
        assert rel == 9.9


class TestBackfillRun:
    def _engine(self, tmp_path):
        from database import Base
        import models  # noqa: F401
        from models import StockAnalysis, MarketDataCache
        from sqlalchemy.orm import sessionmaker
        eng = create_engine(f"sqlite:///{tmp_path}/bf.db")
        Base.metadata.create_all(eng)
        s = sessionmaker(bind=eng)()
        d = date(2026, 10, 15)
        s.add(StockAnalysis(ticker="STX", analysis_date=d, current_price=713.54, day_change_pct=3.35,
                            sector_day_chg=-2.98, relative_strength_1d=6.33, verdict="BUY"))
        s.add(StockAnalysis(ticker="OKAY", analysis_date=d, current_price=100.0, day_change_pct=1.0,
                            sector_day_chg=0.5, relative_strength_1d=0.5, verdict="HOLD"))
        s.add(StockAnalysis(ticker="NOSNAP", analysis_date=d, current_price=10.0, day_change_pct=0.0, verdict="HOLD"))
        s.add(MarketDataCache(ticker="STX", cache_date=d, info_json=json.dumps(STX_OCT14)))
        s.add(MarketDataCache(ticker="OKAY", cache_date=d, info_json=json.dumps({"regularMarketPrice": 100.0, "previousClose": 99.0099})))
        s.commit()
        return eng, s

    def test_dry_run_reports_but_writes_nothing(self, tmp_path):
        eng, s = self._engine(tmp_path)
        summary, fixes = run(eng)
        assert summary["to_fix"] == 1 and summary["already_correct"] == 1 and summary["rows_without_snapshot"] == 1
        assert summary["sign_flips"] == 1
        from models import StockAnalysis
        s.expire_all()
        assert s.query(StockAnalysis).filter_by(ticker="STX").one().day_change_pct == 3.35

    def test_apply_writes_backup_then_fixes_only_the_bad_row(self, tmp_path):
        eng, s = self._engine(tmp_path)
        backup = tmp_path / "old.json"
        run(eng, apply=True, backup=str(backup))
        from models import StockAnalysis
        s.expire_all()
        stx = s.query(StockAnalysis).filter_by(ticker="STX").one()
        assert (stx.day_change_pct, stx.relative_strength_1d) == (-4.5, -1.52)
        assert s.query(StockAnalysis).filter_by(ticker="NOSNAP").one().day_change_pct == 0.0
        saved = json.loads(backup.read_text())
        assert saved == [{"id": stx.id, "ticker": "STX", "analysis_date": "2026-10-15",
                          "old_day_change_pct": 3.35, "new_day_change_pct": -4.5,
                          "old_relative_strength_1d": 6.33, "new_relative_strength_1d": -1.52}]
        summary, _ = run(eng)
        assert summary["to_fix"] == 0  # idempotent

    def test_apply_in_multiple_batches_updates_every_row(self, tmp_path, monkeypatch):
        import backfill_day_change
        from models import StockAnalysis, MarketDataCache
        monkeypatch.setattr(backfill_day_change, "_BATCH", 2)
        eng, s = self._engine(tmp_path)
        d = date(2026, 10, 16)
        for n in range(5):
            t = f"BAT{n}"
            s.add(StockAnalysis(ticker=t, analysis_date=d, current_price=110.0, day_change_pct=0.0, sector_day_chg=1.0, verdict="HOLD"))
            s.add(MarketDataCache(ticker=t, cache_date=d, info_json=json.dumps({"regularMarketPrice": 110.0, "previousClose": 100.0})))
        s.commit()
        run(eng, apply=True, backup=str(tmp_path / "b.json"))
        s.expire_all()
        rows = s.query(StockAnalysis).filter(StockAnalysis.ticker.like("BAT%")).all()
        assert [(r.day_change_pct, r.relative_strength_1d) for r in rows] == [(10.0, 9.0)] * 5
        assert s.query(StockAnalysis).filter_by(ticker="OKAY").one().day_change_pct == 1.0  # untouched


class TestDossierDailyMovesAndDates:
    """Issue #152: the chat built a 'three straight down days' story with one day's move
    ~5x overstated. The dossier history now carries each day's precomputed move, labeled
    with the trading day the price actually closed on (not the pre-market run date)."""

    def _seed(self, db, ticker):
        from models import StockAnalysis, MarketDataCache
        rows = [  # (run date, close, real move, quote timestamp = that trading day 20:00 UTC)
            (date(2026, 10, 13), 753.25, -3.80, 1791835200),
            (date(2026, 10, 14), 747.20, -0.80, 1791921600),
            (date(2026, 10, 15), 713.54, -4.50, 1792008000),
        ]
        for run_d, px, chg, ts in rows:
            db.add(StockAnalysis(ticker=ticker, analysis_date=run_d, current_price=px, day_change_pct=chg, verdict="BUY"))
            db.add(MarketDataCache(ticker=ticker, cache_date=run_d, info_json=json.dumps({"regularMarketTime": ts, "regularMarketPrice": px})))
        db.commit()

    def test_history_lines_carry_trading_date_and_daily_move(self, db_session):
        from services.prompt_builder import build_ticker_dossier
        self._seed(db_session, "DDSTX")
        d = build_ticker_dossier("DDSTX", db_session, "u@example.com")
        assert "Price:          $713.54  ▼4.50% (close of 2026-10-14)" in d
        assert "  2026-10-13 close: $747.20 (▼0.80%) → BUY" in d
        assert "  2026-10-12 close: $753.25 (▼3.80%) → BUY" in d
        assert "2026-10-15 run" not in d

    def test_falls_back_to_run_date_when_no_snapshot(self, db_session):
        from models import StockAnalysis
        from services.prompt_builder import build_ticker_dossier
        for d_, px in ((date(2026, 10, 14), 50.0), (date(2026, 10, 15), 51.0)):
            db_session.add(StockAnalysis(ticker="DDNOSNAP", analysis_date=d_, current_price=px, day_change_pct=1.0, verdict="HOLD"))
        db_session.commit()
        d = build_ticker_dossier("DDNOSNAP", db_session, "u@example.com")
        assert "  2026-10-14 run: $50.00 (▲1.00%) → HOLD" in d
        assert "close of" not in d

    def test_snapshot_from_a_different_quote_is_not_used_for_the_date(self, db_session):
        from models import StockAnalysis, MarketDataCache
        from services.prompt_builder import build_ticker_dossier
        db_session.add(StockAnalysis(ticker="DDMIS", analysis_date=date(2026, 10, 15), current_price=100.0, day_change_pct=1.0, verdict="HOLD"))
        db_session.add(MarketDataCache(ticker="DDMIS", cache_date=date(2026, 10, 15), info_json=json.dumps({"regularMarketTime": 1792008000, "regularMarketPrice": 90.0})))
        db_session.commit()
        assert "close of" not in build_ticker_dossier("DDMIS", db_session, "u@example.com")

    def test_missing_day_change_is_na_not_a_flat_day(self, db_session):
        from services.prompt_builder import _day_move
        assert _day_move(None) == "day change N/A"
        assert _day_move(0.0) == "▲0.00%"
        assert _day_move(-4.5) == "▼4.50%"
