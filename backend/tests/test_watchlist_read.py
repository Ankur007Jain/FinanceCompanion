"""Tests for PATCH /watchlist/{ticker}/read endpoint."""
import uuid
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


GOOD_SECRET = "test-job-secret"


def _mock_user(email: str = "user@example.com"):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


def _email():
    return f"rd-{uuid.uuid4().hex[:8]}@example.com"


def _add(client, email, ticker):
    with _mock_user(email), patch("routers.watchlist._detect_leveraged", return_value=False):
        return client.post(
            "/watchlist",
            params={"id_token": "tok"},
            json={"ticker": ticker, "company_name": "Test Co", "sector": "Tech"},
        )


def _ingest(client, ticker, verdict="HOLD"):
    return client.post(
        "/jobs/ingest-analysis",
        params={"x_job_secret": GOOD_SECRET},
        json={
            "ticker": ticker,
            "analysis_date": str(date.today()),
            "verdict": verdict,
            "current_price": 100.0,
            "reasoning": "Test.",
        },
    )


def _mark_read(client, email, ticker):
    with _mock_user(email):
        return client.patch(f"/watchlist/{ticker}/read", params={"id_token": "tok"})


class TestMarkRead:
    def test_happy_path_returns_ok(self, client: TestClient):
        e = _email()
        _add(client, e, "RDOK")
        _ingest(client, "RDOK")
        r = _mark_read(client, e, "RDOK")
        assert r.status_code == 200
        assert r.json() == {"ok": True, "ticker": "RDOK"}

    def test_ticker_normalized_to_uppercase(self, client: TestClient):
        e = _email()
        _add(client, e, "RDUC")
        _ingest(client, "RDUC")
        with _mock_user(e):
            r = client.patch("/watchlist/rduc/read", params={"id_token": "tok"})
        assert r.status_code == 200
        assert r.json()["ticker"] == "RDUC"

    def test_ticker_not_in_watchlist_returns_404(self, client: TestClient):
        e = _email()
        r = _mark_read(client, e, "RDNX")
        assert r.status_code == 404

    def test_no_auth_returns_401(self, client: TestClient):
        r = client.patch("/watchlist/RDAUTH/read", params={"id_token": "bad-token"})
        assert r.status_code == 401

    def test_sets_last_read_analysis_id_in_db(self, client: TestClient, db_session):
        from models import WatchlistItem, StockAnalysis

        e = _email()
        _add(client, e, "RDDB")
        _ingest(client, "RDDB")

        _mark_read(client, e, "RDDB")

        item = db_session.query(WatchlistItem).filter(
            WatchlistItem.user_email == e,
            WatchlistItem.ticker == "RDDB",
        ).first()
        latest = (
            db_session.query(StockAnalysis)
            .filter(StockAnalysis.ticker == "RDDB")
            .order_by(StockAnalysis.analysis_date.desc())
            .first()
        )
        assert item is not None
        assert item.last_read_analysis_id == latest.id
        assert item.last_read_at is not None

    def test_no_analysis_returns_ok_without_writing(self, client: TestClient, db_session):
        from models import WatchlistItem

        e = _email()
        _add(client, e, "RDNA")
        r = _mark_read(client, e, "RDNA")
        assert r.status_code == 200
        assert r.json()["ok"] is True

        item = db_session.query(WatchlistItem).filter(
            WatchlistItem.user_email == e,
            WatchlistItem.ticker == "RDNA",
        ).first()
        assert item.last_read_analysis_id is None
        assert item.last_read_at is None

    def test_user_scoped_cannot_read_other_users_ticker(self, client: TestClient):
        e1, e2 = _email(), _email()
        _add(client, e1, "RDSC")
        _ingest(client, "RDSC")
        r = _mark_read(client, e2, "RDSC")
        assert r.status_code == 404
