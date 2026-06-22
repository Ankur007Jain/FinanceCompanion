"""Tests for GET /watchlist — list user's watchlist items."""
import uuid
from unittest.mock import patch

GOOD_SECRET = "test-job-secret"


def _email():
    return f"list-{uuid.uuid4().hex[:8]}@example.com"


def _mock_user(email):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


def _add(client, email, ticker):
    with _mock_user(email), patch("routers.watchlist._detect_leveraged", return_value=False):
        return client.post(
            "/watchlist",
            params={"id_token": "tok"},
            json={"ticker": ticker, "company_name": "Test Co", "sector": "Tech"},
        )


def _list(client, email):
    with _mock_user(email):
        return client.get("/watchlist", params={"id_token": "tok"})


def test_empty_watchlist_returns_empty_list(client):
    r = _list(client, _email())
    assert r.status_code == 200
    assert r.json() == []


def test_list_returns_added_tickers(client):
    e = _email()
    _add(client, e, "LSTX")
    _add(client, e, "LSTY")
    r = _list(client, e)
    assert r.status_code == 200
    tickers = {item["ticker"] for item in r.json()}
    assert {"LSTX", "LSTY"} == tickers


def test_list_is_user_scoped(client):
    e1, e2 = _email(), _email()
    _add(client, e1, "LSCA")
    r = _list(client, e2)
    tickers = {item["ticker"] for item in r.json()}
    assert "LSCA" not in tickers


def test_list_shows_company_name(client):
    e = _email()
    with _mock_user(e), patch("routers.watchlist._detect_leveraged", return_value=False):
        client.post("/watchlist", params={"id_token": "tok"},
                    json={"ticker": "LSNM", "company_name": "Test Corp", "sector": "Tech"})
    r = _list(client, e)
    item = next(i for i in r.json() if i["ticker"] == "LSNM")
    assert item["company_name"] == "Test Corp"


def test_list_reflects_delete(client):
    e = _email()
    _add(client, e, "LSDL")
    with _mock_user(e):
        client.delete("/watchlist/LSDL", params={"id_token": "tok"})
    r = _list(client, e)
    tickers = {item["ticker"] for item in r.json()}
    assert "LSDL" not in tickers


def test_unauthenticated_returns_401(client):
    r = client.get("/watchlist", params={"id_token": "bad-token"})
    assert r.status_code == 401
