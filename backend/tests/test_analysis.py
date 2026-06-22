"""
Tests for /analysis endpoints: digest, latest, history.
Covers user isolation, no-analysis state, and field fidelity.
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


GOOD_SECRET = "test-job-secret"

def _mock_user(email: str = "user@example.com"):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )

def _ingest(client, ticker: str, verdict: str = "HOLD", analysis_date: str | None = None, **extra):
    payload = {
        "ticker": ticker,
        "analysis_date": analysis_date or str(date.today()),
        "verdict": verdict,
        "current_price": 100.0,
        "reasoning": "Test reasoning.",
        **extra,
    }
    return client.post(
        "/jobs/ingest-analysis",
        params={"x_job_secret": GOOD_SECRET},
        json=payload,
    )


class TestDigest:
    def test_empty_watchlist_returns_empty_list(self, client: TestClient):
        with _mock_user("empty@example.com"):
            r = client.get("/analysis/digest", params={"id_token": "fake"})
        assert r.status_code == 200
        assert r.json() == []

    def test_ticker_with_no_analysis_shows_pending(self, client: TestClient):
        with _mock_user("pending@example.com"):
            client.post("/watchlist", params={"id_token": "fake"},
                        json={"ticker": "PEND", "is_leveraged": False})
            r = client.get("/analysis/digest", params={"id_token": "fake"})
        items = r.json()
        assert len(items) == 1
        assert items[0]["ticker"] == "PEND"
        assert items[0]["analysis"] is None

    def test_digest_shows_todays_analysis(self, client: TestClient):
        _ingest(client, "DGTS", "BUY")
        with _mock_user("digest2@example.com"):
            client.post("/watchlist", params={"id_token": "fake"},
                        json={"ticker": "DGTS", "is_leveraged": False})
            r = client.get("/analysis/digest", params={"id_token": "fake"})
        items = r.json()
        assert len(items) == 1
        assert items[0]["analysis"] is not None
        assert items[0]["analysis"]["verdict"] == "BUY"

    def test_digest_does_not_show_yesterdays_analysis(self, client: TestClient):
        yesterday = str(date.today() - timedelta(days=1))
        _ingest(client, "YEST", "SELL", analysis_date=yesterday)
        with _mock_user("yest@example.com"):
            client.post("/watchlist", params={"id_token": "fake"},
                        json={"ticker": "YEST", "is_leveraged": False})
            r = client.get("/analysis/digest", params={"id_token": "fake"})
        items = r.json()
        assert items[0]["analysis"] is None

    def test_digest_is_user_scoped(self, client: TestClient):
        _ingest(client, "SCOP", "HOLD")
        with _mock_user("userA@example.com"):
            client.post("/watchlist", params={"id_token": "fake"},
                        json={"ticker": "SCOP", "is_leveraged": False})
            rA = client.get("/analysis/digest", params={"id_token": "fake"})

        with _mock_user("userB@example.com"):
            rB = client.get("/analysis/digest", params={"id_token": "fake"})

        assert len(rA.json()) == 1
        assert len(rB.json()) == 0

    def test_unauthenticated_returns_401(self, client: TestClient):
        r = client.get("/analysis/digest", params={"id_token": "bad-token"})
        assert r.status_code == 401


class TestLatest:
    def test_no_analysis_returns_404(self, client: TestClient):
        with _mock_user():
            r = client.get("/analysis/NOANAL/latest", params={"id_token": "fake"})
        assert r.status_code == 404

    def test_returns_most_recent_analysis(self, client: TestClient):
        yesterday = str(date.today() - timedelta(days=1))
        _ingest(client, "LATEST1", "SELL", analysis_date=yesterday)
        _ingest(client, "LATEST1", "BUY")
        with _mock_user():
            r = client.get("/analysis/LATEST1/latest", params={"id_token": "fake"})
        assert r.status_code == 200
        assert r.json()["verdict"] == "BUY"

    def test_ticker_is_case_insensitive(self, client: TestClient):
        _ingest(client, "CASE1", "WATCH")
        with _mock_user():
            r = client.get("/analysis/case1/latest", params={"id_token": "fake"})
        assert r.status_code == 200
        assert r.json()["verdict"] == "WATCH"

    def test_fundamentals_fields_returned(self, client: TestClient):
        _ingest(client, "FUND1", "BUY",
                pe_trailing=25.0, beta=1.2, sector="Technology",
                market_cap=500_000_000_000.0, short_float_pct=0.05)
        with _mock_user():
            r = client.get("/analysis/FUND1/latest", params={"id_token": "fake"})
        data = r.json()
        assert data["pe_trailing"] == pytest.approx(25.0)
        assert data["beta"] == pytest.approx(1.2)
        assert data["sector"] == "Technology"
        assert data["market_cap"] == pytest.approx(500_000_000_000.0)

    def test_stop_loss_hold_period_returned(self, client: TestClient):
        _ingest(client, "STOP1", "BUY", stop_loss=95.0, hold_period="1-2 weeks")
        with _mock_user():
            r = client.get("/analysis/STOP1/latest", params={"id_token": "fake"})
        data = r.json()
        assert data["stop_loss"] == pytest.approx(95.0)
        assert data["hold_period"] == "1-2 weeks"

    def test_committee_fields_returned(self, client: TestClient):
        _ingest(client, "COMM1", "BUY",
                conviction_score=82, risk_level="MED", confidence="High",
                bull_case="Strong free cash flow funds buybacks.",
                bear_case="A pricey multiple leaves no room for a miss.",
                thesis_invalidation="A guidance cut on the next earnings call.")
        with _mock_user():
            r = client.get("/analysis/COMM1/latest", params={"id_token": "fake"})
        data = r.json()
        assert data["conviction_score"] == 82
        assert data["risk_level"] == "MED"
        assert data["confidence"] == "High"
        assert "free cash flow" in data["bull_case"]
        assert "pricey multiple" in data["bear_case"]
        assert "guidance cut" in data["thesis_invalidation"]


class TestHistory:
    def test_unknown_ticker_returns_empty(self, client: TestClient):
        with _mock_user():
            r = client.get("/analysis/ZZUNKNOWN/history", params={"id_token": "fake"})
        assert r.status_code == 200
        assert r.json() == []

    def test_history_sorted_newest_first(self, client: TestClient):
        for days_ago in (3, 2, 1):
            d = str(date.today() - timedelta(days=days_ago))
            _ingest(client, "HSORT1", analysis_date=d,
                    verdict=["SELL", "HOLD", "BUY"][3 - days_ago])
        with _mock_user():
            r = client.get("/analysis/HSORT1/history", params={"id_token": "fake"})
        verdicts = [x["verdict"] for x in r.json()]
        assert verdicts == ["BUY", "HOLD", "SELL"]

    def test_history_respects_days_limit(self, client: TestClient):
        for days_ago in range(1, 6):
            d = str(date.today() - timedelta(days=days_ago))
            _ingest(client, "HLIMIT1", analysis_date=d, verdict="HOLD")
        with _mock_user():
            r = client.get("/analysis/HLIMIT1/history",
                           params={"id_token": "fake", "days": 3})
        assert len(r.json()) == 3


class TestAdminTickers:
    def test_bad_secret_returns_401(self, client: TestClient):
        r = client.get("/jobs/admin/tickers", params={"x_admin_secret": "wrong"})
        assert r.status_code == 401

    def test_returns_distinct_tickers_across_users(self, client: TestClient):
        import os
        os.environ["ADMIN_SECRET"] = "test-admin-secret"

        for email in ("adminA@example.com", "adminB@example.com"):
            with _mock_user(email):
                client.post("/watchlist", params={"id_token": "fake"},
                            json={"ticker": "SHRD", "is_leveraged": False})

        r = client.get("/jobs/admin/tickers", params={"x_admin_secret": "test-admin-secret"})
        assert r.status_code == 200
        tickers = r.json()["tickers"]
        assert tickers.count("SHRD") == 1
