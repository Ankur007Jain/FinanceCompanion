"""Tests for GET /analysis/important endpoint."""
import uuid
from datetime import date, timedelta
from unittest.mock import patch


GOOD_SECRET = "test-job-secret"


def _email():
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


def _mock_user(email):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


def _add_watchlist(client, email, ticker):
    with _mock_user(email), patch("routers.watchlist._detect_leveraged", return_value=False):
        client.post("/watchlist", params={"id_token": "tok"},
                    json={"ticker": ticker, "company_name": "Co", "sector": "Tech"})


def _ingest(client, ticker, important=False, verdict="BUY", days_ago=0):
    analysis_date = (date.today() - timedelta(days=days_ago)).isoformat()
    client.post(
        "/jobs/ingest-analysis",
        params={"x_job_secret": GOOD_SECRET},
        json={
            "ticker": ticker, "analysis_date": analysis_date,
            "verdict": verdict, "current_price": 100.0,
            "price_change_pct": 1.0, "week52_high": 120.0, "week52_low": 80.0,
            "week52_position_pct": 50.0, "ma50": 98.0, "ma200": 95.0, "rsi": 55.0,
            "analyst_consensus": "BUY", "reasoning": "test",
            "is_important_day": important,
            "importance_reason": "earnings beat" if important else "",
        },
    )


def test_important_empty_watchlist(client):
    e = _email()
    with _mock_user(e):
        r = client.get("/analysis/important", params={"id_token": "tok"})
    assert r.status_code == 200
    assert r.json() == []


def test_important_returns_only_important_days(client):
    e = _email()
    _add_watchlist(client, e, "AAPL")
    _ingest(client, "AAPL", important=True)
    _ingest(client, "AAPL", important=False, days_ago=1)
    with _mock_user(e):
        r = client.get("/analysis/important", params={"id_token": "tok"})
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["is_important_day"] is True


def test_important_only_user_watchlist_tickers(client):
    e1, e2 = _email(), _email()
    _add_watchlist(client, e1, "TSLA")
    _add_watchlist(client, e2, "NVDA")
    _ingest(client, "TSLA", important=True)
    _ingest(client, "NVDA", important=True)
    with _mock_user(e1):
        r = client.get("/analysis/important", params={"id_token": "tok"})
    tickers = {x["ticker"] for x in r.json()}
    assert "TSLA" in tickers
    assert "NVDA" not in tickers


def test_important_respects_days_filter(client):
    e = _email()
    _add_watchlist(client, e, "MSFT")
    _ingest(client, "MSFT", important=True, days_ago=0)
    _ingest(client, "MSFT", important=True, days_ago=40)
    with _mock_user(e):
        r = client.get("/analysis/important", params={"id_token": "tok", "days": "30"})
    assert len(r.json()) == 1


def test_important_returns_200_no_important_days(client):
    e = _email()
    _add_watchlist(client, e, "GOOG")
    _ingest(client, "GOOG", important=False)
    with _mock_user(e):
        r = client.get("/analysis/important", params={"id_token": "tok"})
    assert r.status_code == 200
    assert r.json() == []
