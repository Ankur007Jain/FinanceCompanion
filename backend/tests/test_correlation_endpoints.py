"""
Tests for GET /jobs/admin/closes and POST /jobs/ingest-correlations —
the two endpoints scripts/compute_correlations.py depends on.
"""
import json
import os
from datetime import date, timedelta

from fastapi.testclient import TestClient

from models import MarketDataCache, TickerControl, TickerCorrelation, WatchlistItem

ADMIN_SECRET = "test-admin-secret"
JOB_SECRET = "test-job-secret"


class TestGetCloses:
    def test_rejects_bad_secret(self, client: TestClient):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        r = client.get("/jobs/admin/closes", params={"x_admin_secret": "nope"})
        assert r.status_code == 401

    def test_extracts_closes_from_records_format(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        db_session.add(WatchlistItem(user_email="u@example.com", ticker="CLOSA"))
        history = json.dumps([
            {"Date": "2026-01-01", "Open": 10, "High": 11, "Low": 9, "Close": 10.5, "Volume": 1000},
            {"Date": "2026-01-02", "Open": 10.5, "High": 12, "Low": 10, "Close": 11.2, "Volume": 1200},
        ])
        db_session.add(MarketDataCache(ticker="CLOSA", cache_date=date.today(), history_json=history))
        db_session.commit()

        r = client.get("/jobs/admin/closes", params={"x_admin_secret": ADMIN_SECRET, "days": 200})
        assert r.status_code == 200
        closes = r.json()["closes"]
        assert closes["CLOSA"] == {"2026-01-01": 10.5, "2026-01-02": 11.2}

    def test_extracts_closes_from_split_format(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        db_session.add(WatchlistItem(user_email="u@example.com", ticker="CLOSB"))
        history = json.dumps({
            "columns": ["Open", "High", "Low", "Close", "Volume"],
            "index": ["2026-01-01T00:00:00", "2026-01-02T00:00:00"],
            "data": [[10, 11, 9, 10.5, 1000], [10.5, 12, 10, 11.2, 1200]],
        })
        db_session.add(MarketDataCache(ticker="CLOSB", cache_date=date.today(), history_json=history))
        db_session.commit()

        r = client.get("/jobs/admin/closes", params={"x_admin_secret": ADMIN_SECRET, "days": 200})
        assert r.status_code == 200
        closes = r.json()["closes"]
        assert closes["CLOSB"] == {"2026-01-01": 10.5, "2026-01-02": 11.2}

    def test_excludes_disabled_tickers(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        db_session.add(WatchlistItem(user_email="u@example.com", ticker="CLOSDIS"))
        db_session.add(TickerControl(ticker="CLOSDIS", analysis_enabled=False))
        history = json.dumps([{"Date": "2026-01-01", "Close": 10.0}])
        db_session.add(MarketDataCache(ticker="CLOSDIS", cache_date=date.today(), history_json=history))
        db_session.commit()

        r = client.get("/jobs/admin/closes", params={"x_admin_secret": ADMIN_SECRET})
        assert "CLOSDIS" not in r.json()["closes"]

    def test_ticker_with_no_cache_omitted_not_crashed(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        db_session.add(WatchlistItem(user_email="u@example.com", ticker="CLOSNONE"))
        db_session.commit()
        r = client.get("/jobs/admin/closes", params={"x_admin_secret": ADMIN_SECRET})
        assert r.status_code == 200
        assert "CLOSNONE" not in r.json()["closes"]

    def test_days_window_excludes_old_closes(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        db_session.add(WatchlistItem(user_email="u@example.com", ticker="CLOSOLD"))
        old_date = (date.today() - timedelta(days=500)).isoformat()
        recent_date = date.today().isoformat()
        history = json.dumps([
            {"Date": old_date, "Close": 1.0},
            {"Date": recent_date, "Close": 2.0},
        ])
        db_session.add(MarketDataCache(ticker="CLOSOLD", cache_date=date.today(), history_json=history))
        db_session.commit()

        r = client.get("/jobs/admin/closes", params={"x_admin_secret": ADMIN_SECRET, "days": 30})
        closes = r.json()["closes"]["CLOSOLD"]
        assert old_date not in closes
        assert recent_date in closes


class TestIngestCorrelations:
    def test_rejects_bad_secret(self, client: TestClient):
        r = client.post(
            "/jobs/ingest-correlations",
            params={"x_job_secret": "wrong"},
            json={"computed_date": str(date.today()), "pairs": []},
        )
        assert r.status_code == 401

    def test_saves_pairs(self, client: TestClient, db_session):
        payload = {
            "computed_date": str(date.today()),
            "pairs": [
                {"ticker_a": "AAA", "ticker_b": "BBB", "corr_30d": 0.5, "corr_90d": 0.6,
                 "corr_180d": 0.55, "p_value_90d": 0.001, "significant": True},
            ],
        }
        r = client.post("/jobs/ingest-correlations", params={"x_job_secret": JOB_SECRET}, json=payload)
        assert r.status_code == 200
        assert r.json()["pairs"] == 1

        db_session.expire_all()
        row = db_session.get(TickerCorrelation, ("AAA", "BBB"))
        assert row.corr_90d == 0.6
        assert row.significant is True

    def test_full_recompute_replaces_same_date_pairs(self, client: TestClient, db_session):
        d = str(date.today())
        first = {"computed_date": d, "pairs": [
            {"ticker_a": "CCC", "ticker_b": "DDD", "corr_90d": 0.3, "significant": False},
        ]}
        client.post("/jobs/ingest-correlations", params={"x_job_secret": JOB_SECRET}, json=first)

        # Second run for the same date doesn't include CCC/DDD anymore — it should disappear,
        # not linger as a stale pair from a ticker that dropped out of every watchlist.
        second = {"computed_date": d, "pairs": [
            {"ticker_a": "EEE", "ticker_b": "FFF", "corr_90d": 0.7, "significant": True},
        ]}
        client.post("/jobs/ingest-correlations", params={"x_job_secret": JOB_SECRET}, json=second)

        db_session.expire_all()
        assert db_session.get(TickerCorrelation, ("CCC", "DDD")) is None
        assert db_session.get(TickerCorrelation, ("EEE", "FFF")) is not None
