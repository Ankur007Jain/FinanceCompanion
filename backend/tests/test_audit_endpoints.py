"""
Tests for the audit-agent endpoints: verdict-history (Scorecard), data-quality
(Sentinel), and memory lesson append (Scorecard → memory feedback loop).
"""
import os
from datetime import date, timedelta

from fastapi.testclient import TestClient

from models import StockAnalysis, StockMemory, WatchlistItem

ADMIN_SECRET = "test-admin-secret"


def _seed(db, ticker, d, **extra):
    a = StockAnalysis(
        ticker=ticker, analysis_date=d, verdict=extra.pop("verdict", "BUY"),
        current_price=100.0, conviction_score=70,
        entry_target=98.0, exit_target=115.0, stop_loss=92.0, **extra,
    )
    db.add(a)
    db.commit()
    return a


class TestVerdictHistory:
    def test_rejects_bad_secret(self, client: TestClient):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        r = client.get("/jobs/admin/verdict-history", params={"x_admin_secret": "nope"})
        assert r.status_code == 401

    def test_returns_verdicts_with_targets(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        _seed(db_session, "SCHA", date.today() - timedelta(days=3))
        r = client.get("/jobs/admin/verdict-history", params={"x_admin_secret": ADMIN_SECRET})
        assert r.status_code == 200
        row = next(a for a in r.json()["analyses"] if a["ticker"] == "SCHA")
        assert row["verdict"] == "BUY"
        assert row["exit_target"] == 115.0
        assert row["stop_loss"] == 92.0
        assert row["conviction"] == 70

    def test_days_window_excludes_old_rows(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        _seed(db_session, "SCHB", date.today() - timedelta(days=60))
        r = client.get("/jobs/admin/verdict-history", params={"x_admin_secret": ADMIN_SECRET, "days": 45})
        assert all(a["ticker"] != "SCHB" for a in r.json()["analyses"])


class TestDataQuality:
    def test_rejects_bad_secret(self, client: TestClient):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        r = client.get("/jobs/admin/data-quality", params={"x_admin_secret": "nope"})
        assert r.status_code == 401

    def test_null_rates_and_missing_tickers(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        today = date.today()
        # DQTA has fundamentals, DQTB doesn't — 50% null rate for pe_trailing today
        _seed(db_session, "DQTA", today, pe_trailing=20.0, rsi=50.0)
        _seed(db_session, "DQTB", today)
        # DQTC is watchlisted but absent from today's run
        db_session.add(WatchlistItem(user_email="dq@example.com", ticker="DQTC"))
        db_session.commit()

        r = client.get("/jobs/admin/data-quality", params={"x_admin_secret": ADMIN_SECRET})
        assert r.status_code == 200
        body = r.json()
        assert body["latest_date"] == today.isoformat()
        day = body["null_rates_by_date"][today.isoformat()]
        assert day["rows"] >= 2
        assert 0 < day["null_pct"]["pe_trailing"] < 100
        assert "DQTC" in body["missing_in_latest"]


class TestMemoryLesson:
    def test_rejects_bad_secret(self, client: TestClient):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        r = client.post("/jobs/admin/memories/LESA/lesson", params={"x_admin_secret": "nope"}, json={"lesson": "x"})
        assert r.status_code == 401

    def test_rejects_empty_lesson(self, client: TestClient):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        r = client.post("/jobs/admin/memories/LESA/lesson", params={"x_admin_secret": ADMIN_SECRET}, json={"lesson": "  "})
        assert r.status_code == 422

    def test_appends_to_existing_memory(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        db_session.merge(StockMemory(ticker="LESB", memory_narrative="Existing context."))
        db_session.commit()
        r = client.post(
            "/jobs/admin/memories/lesb/lesson",
            params={"x_admin_secret": ADMIN_SECRET},
            json={"lesson": "3 BUYs stopped out at $92 between Jul 1-4; oversold RSI kept falling."},
        )
        assert r.status_code == 200
        db_session.expire_all()
        mem = db_session.get(StockMemory, "LESB").memory_narrative
        assert mem.startswith("Existing context.")
        assert "[Scorecard] 3 BUYs stopped out" in mem

    def test_creates_memory_when_missing(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        r = client.post(
            "/jobs/admin/memories/LESC/lesson",
            params={"x_admin_secret": ADMIN_SECRET},
            json={"lesson": "First lesson."},
        )
        assert r.status_code == 200
        db_session.expire_all()
        assert db_session.get(StockMemory, "LESC").memory_narrative == "[Scorecard] First lesson."

    def test_caps_total_length(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        db_session.merge(StockMemory(ticker="LESD", memory_narrative="x" * 1150))
        db_session.commit()
        r = client.post(
            "/jobs/admin/memories/LESD/lesson",
            params={"x_admin_secret": ADMIN_SECRET},
            json={"lesson": "y" * 500},
        )
        assert r.status_code == 200
        assert r.json()["memory_chars"] <= 1200
