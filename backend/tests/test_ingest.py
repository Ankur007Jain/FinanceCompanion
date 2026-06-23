"""
Tests for POST /jobs/ingest-analysis and GET /jobs/admin/analyzed-today.
Covers field mapping, upsert logic, fundamentals, and secret validation.
"""
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient


GOOD_SECRET = "test-job-secret"
ADMIN_SECRET = "test-admin-secret"

_BASE = {
    "ticker": "TSLA",
    "analysis_date": str(date.today()),
    "verdict": "BUY",
    "current_price": 250.00,
    "price_change_pct": 1.5,
    "week52_high": 300.00,
    "week52_low": 150.00,
    "week52_position_pct": 66.7,
    "ma50": 240.00,
    "ma200": 220.00,
    "rsi": 58.5,
    "analyst_consensus": "BUY",
    "entry_target": 245.00,
    "exit_target": 290.00,
    "stop_loss": 230.00,
    "hold_period": "2-4 weeks",
    "reasoning": "Strong momentum and improving margins.",
    "news_summary": "Tesla beats Q4 deliveries estimate.",
    "ripple_analysis": "Positive for EV supply chain.",
    "is_important_day": False,
    "importance_reason": "",
}

_FUNDAMENTALS = {
    "pe_trailing": 45.2,
    "pe_forward": 30.1,
    "revenue_growth": 0.19,
    "earnings_growth": 0.25,
    "profit_margin": 0.15,
    "debt_to_equity": 0.8,
    "free_cashflow": 4_500_000_000.0,
    "return_on_equity": 0.22,
    "beta": 2.1,
    "short_float_pct": 0.03,
    "short_ratio": 1.5,
    "inst_ownership_pct": 0.65,
    "insider_ownership_pct": 0.14,
    "sp500_52w_change": 0.25,
    "stock_52w_change": 0.42,
    "dividend_yield": None,
    "market_cap": 800_000_000_000.0,
    "sector": "Consumer Cyclical",
    "industry": "Auto Manufacturers",
}


class TestIngestSecurity:
    def test_bad_secret_returns_401(self, client: TestClient):
        r = client.post(
            "/jobs/ingest-analysis",
            params={"x_job_secret": "wrong"},
            json=_BASE,
        )
        assert r.status_code == 401

    def test_missing_secret_returns_401(self, client: TestClient):
        r = client.post("/jobs/ingest-analysis", json=_BASE)
        assert r.status_code == 401

    def test_good_secret_accepted(self, client: TestClient):
        payload = {**_BASE, "ticker": "AMZN", "analysis_date": str(date.today() - timedelta(days=5))}
        r = client.post(
            "/jobs/ingest-analysis",
            params={"x_job_secret": GOOD_SECRET},
            json=payload,
        )
        assert r.status_code == 200
        assert r.json()["status"] in ("created", "updated")


class TestIngestCreate:
    def test_creates_new_analysis(self, client: TestClient):
        payload = {**_BASE, "ticker": "GOOGL", "analysis_date": str(date.today())}
        r = client.post(
            "/jobs/ingest-analysis",
            params={"x_job_secret": GOOD_SECRET},
            json=payload,
        )
        assert r.status_code == 200
        assert r.json() == {"status": "created", "ticker": "GOOGL"}

    def test_fundamentals_are_persisted(self, client: TestClient):
        from fastapi.testclient import TestClient
        from routers.auth import get_current_user
        from unittest.mock import patch

        payload = {**_BASE, **_FUNDAMENTALS, "ticker": "MSFT", "analysis_date": str(date.today())}
        r = client.post(
            "/jobs/ingest-analysis",
            params={"x_job_secret": GOOD_SECRET},
            json=payload,
        )
        assert r.status_code == 200

        # Retrieve and verify fundamentals via /analysis endpoint
        with patch("routers.auth.id_token.verify_oauth2_token",
                   return_value={"email": "fund@example.com", "name": "Fund"}):
            r2 = client.get("/analysis/MSFT/latest", params={"id_token": "fake"})
        assert r2.status_code == 200
        data = r2.json()
        assert data["pe_trailing"] == pytest.approx(45.2, rel=1e-3)
        assert data["pe_forward"] == pytest.approx(30.1, rel=1e-3)
        assert data["revenue_growth"] == pytest.approx(0.19, rel=1e-3)
        assert data["profit_margin"] == pytest.approx(0.15, rel=1e-3)
        assert data["beta"] == pytest.approx(2.1, rel=1e-3)
        assert data["short_float_pct"] == pytest.approx(0.03, rel=1e-3)
        assert data["inst_ownership_pct"] == pytest.approx(0.65, rel=1e-3)
        assert data["market_cap"] == pytest.approx(800_000_000_000.0, rel=1e-3)
        assert data["sector"] == "Consumer Cyclical"
        assert data["industry"] == "Auto Manufacturers"

    def test_stop_loss_and_hold_period_persisted(self, client: TestClient):
        from unittest.mock import patch

        payload = {**_BASE, "ticker": "NVDA", "analysis_date": str(date.today()),
                   "stop_loss": 460.00, "hold_period": "3-5 days"}
        client.post("/jobs/ingest-analysis", params={"x_job_secret": GOOD_SECRET}, json=payload)

        with patch("routers.auth.id_token.verify_oauth2_token",
                   return_value={"email": "sl@example.com", "name": "SL"}):
            r = client.get("/analysis/NVDA/latest", params={"id_token": "fake"})
        data = r.json()
        assert data["stop_loss"] == pytest.approx(460.00)
        assert data["hold_period"] == "3-5 days"

    def test_is_important_day_flag(self, client: TestClient):
        from unittest.mock import patch

        payload = {**_BASE, "ticker": "MRVL", "analysis_date": str(date.today()),
                   "is_important_day": True, "importance_reason": "Earnings beat, verdict reversal"}
        client.post("/jobs/ingest-analysis", params={"x_job_secret": GOOD_SECRET}, json=payload)

        with patch("routers.auth.id_token.verify_oauth2_token",
                   return_value={"email": "imp@example.com", "name": "Imp"}):
            r = client.get("/analysis/MRVL/latest", params={"id_token": "fake"})
        data = r.json()
        assert data["is_important_day"] is True
        assert "reversal" in data["importance_reason"]


class TestIngestUpsert:
    def test_duplicate_ingest_updates_not_duplicates(self, client: TestClient):
        from unittest.mock import patch

        payload = {**_BASE, "ticker": "META", "analysis_date": str(date.today()),
                   "verdict": "HOLD", "reasoning": "First pass."}
        client.post("/jobs/ingest-analysis", params={"x_job_secret": GOOD_SECRET}, json=payload)

        payload2 = {**payload, "verdict": "BUY", "reasoning": "Updated with new data."}
        r = client.post("/jobs/ingest-analysis", params={"x_job_secret": GOOD_SECRET}, json=payload2)
        assert r.json()["status"] == "updated"

        with patch("routers.auth.id_token.verify_oauth2_token",
                   return_value={"email": "meta@example.com", "name": "Meta"}):
            hist = client.get("/analysis/META/history", params={"id_token": "fake"})
        assert len(hist.json()) == 1
        assert hist.json()[0]["verdict"] == "BUY"

    def test_different_dates_create_separate_rows(self, client: TestClient):
        from unittest.mock import patch

        yesterday = str(date.today() - timedelta(days=1))
        today = str(date.today())
        for d in (yesterday, today):
            client.post("/jobs/ingest-analysis", params={"x_job_secret": GOOD_SECRET},
                        json={**_BASE, "ticker": "AAPL2", "analysis_date": d})

        with patch("routers.auth.id_token.verify_oauth2_token",
                   return_value={"email": "dates@example.com", "name": "Dates"}):
            hist = client.get("/analysis/AAPL2/history", params={"id_token": "fake"})
        assert len(hist.json()) == 2


class TestAnalyzedToday:
    def test_bad_admin_secret_returns_401(self, client: TestClient):
        r = client.get("/jobs/admin/analyzed-today", params={"x_admin_secret": "bad"})
        assert r.status_code == 401

    def test_analyzed_today_includes_ingested_ticker(self, client: TestClient):
        import os
        os.environ["ADMIN_SECRET"] = "test-admin-secret"

        payload = {**_BASE, "ticker": "SNAP", "analysis_date": str(date.today())}
        client.post("/jobs/ingest-analysis", params={"x_job_secret": GOOD_SECRET}, json=payload)

        r = client.get("/jobs/admin/analyzed-today", params={"x_admin_secret": "test-admin-secret"})
        assert r.status_code == 200
        assert "SNAP" in r.json()["analyzed"]
        assert r.json()["date"] == str(date.today())

    def test_analyzed_today_excludes_old_dates(self, client: TestClient):
        import os
        os.environ["ADMIN_SECRET"] = "test-admin-secret"

        payload = {**_BASE, "ticker": "OLD1", "analysis_date": str(date.today() - timedelta(days=1))}
        client.post("/jobs/ingest-analysis", params={"x_job_secret": GOOD_SECRET}, json=payload)

        r = client.get("/jobs/admin/analyzed-today", params={"x_admin_secret": "test-admin-secret"})
        assert "OLD1" not in r.json()["analyzed"]


class TestIngestSnapshot:
    def test_snapshot_saves_and_returns_saved(self, client: TestClient):
        payload = {
            "ticker": "SNAP1",
            "cache_date": str(date.today()),
            "info_json": '{"currentPrice": 100.0}',
            "history_json": '[{"Date": "2026-01-01", "Close": 99.0}]',
            "news_json": '[{"title": "SNAP1 earnings beat"}]',
            "calendar_json": '{"Earnings Date": ["2026-07-15"]}',
        }
        r = client.post("/jobs/ingest-snapshot", params={"x_job_secret": GOOD_SECRET}, json=payload)
        assert r.status_code == 200
        assert r.json()["status"] == "saved"
        assert r.json()["ticker"] == "SNAP1"

    def test_snapshot_rejects_bad_secret(self, client: TestClient):
        payload = {"ticker": "X", "cache_date": str(date.today())}
        r = client.post("/jobs/ingest-snapshot", params={"x_job_secret": "wrong"}, json=payload)
        assert r.status_code == 401

    def test_snapshot_upserts_on_same_date(self, client: TestClient):
        payload = {
            "ticker": "UPSRT",
            "cache_date": str(date.today()),
            "info_json": '{"currentPrice": 50.0}',
        }
        r1 = client.post("/jobs/ingest-snapshot", params={"x_job_secret": GOOD_SECRET}, json=payload)
        assert r1.status_code == 200

        payload["info_json"] = '{"currentPrice": 55.0}'
        r2 = client.post("/jobs/ingest-snapshot", params={"x_job_secret": GOOD_SECRET}, json=payload)
        assert r2.status_code == 200
        assert r2.json()["status"] == "saved"

    def test_snapshot_accepts_null_fields(self, client: TestClient):
        payload = {"ticker": "MINML", "cache_date": str(date.today())}
        r = client.post("/jobs/ingest-snapshot", params={"x_job_secret": GOOD_SECRET}, json=payload)
        assert r.status_code == 200
