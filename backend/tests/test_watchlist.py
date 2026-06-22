"""Tests for POST /watchlist ticker validation and DELETE /watchlist/{ticker}."""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _mock_user(email: str = "user@example.com"):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


def _add(client, ticker: str):
    with _mock_user():
        return client.post(
            "/watchlist",
            params={"id_token": "tok"},
            json={"ticker": ticker, "company_name": "Test Co", "sector": "Tech"},
        )


@pytest.mark.parametrize("ticker", ["AAPL", "TSLA", "GOOGL", "BRK.B", "BF-B", "A"])
def test_valid_tickers_accepted(client, ticker):
    with patch("routers.watchlist._detect_leveraged", return_value=False):
        r = _add(client, ticker)
    assert r.status_code == 200, r.json()


@pytest.mark.parametrize("ticker", [
    "",           # empty
    "TOOLONG",    # 7 chars
    "123",        # digits only
    "AA PL",      # space
    "AAPL!",      # special char
])
def test_invalid_tickers_rejected(client, ticker):
    r = _add(client, ticker)
    assert r.status_code == 400


def test_ticker_normalized_to_uppercase(client):
    with patch("routers.watchlist._detect_leveraged", return_value=False):
        r = _add(client, "msft")
    assert r.status_code == 200
    assert r.json()["ticker"] == "MSFT"


def test_duplicate_ticker_returns_409(client):
    with patch("routers.watchlist._detect_leveraged", return_value=False):
        _add(client, "NVDA")
        r = _add(client, "NVDA")
    assert r.status_code == 409


def _email():
    return f"del-{uuid.uuid4().hex[:8]}@example.com"


def _add_as(client, email, ticker):
    with _mock_user(email), patch("routers.watchlist._detect_leveraged", return_value=False):
        return client.post("/watchlist", params={"id_token": "tok"},
                           json={"ticker": ticker, "company_name": "Co", "sector": "Tech"})


def _delete(client, email, ticker):
    with _mock_user(email):
        return client.delete(f"/watchlist/{ticker}", params={"id_token": "tok"})


def test_delete_removes_ticker(client):
    e = _email()
    _add_as(client, e, "DELX")
    r = _delete(client, e, "DELX")
    assert r.status_code == 200
    assert r.json()["deleted"] == "DELX"


def test_delete_not_in_watchlist_returns_404(client):
    e = _email()
    r = _delete(client, e, "ZZZZ")
    assert r.status_code == 404


def test_delete_is_user_scoped(client):
    e1, e2 = _email(), _email()
    _add_as(client, e1, "DSCOP")
    r = _delete(client, e2, "DSCOP")
    assert r.status_code == 404


def test_delete_ticker_case_insensitive(client):
    e = _email()
    _add_as(client, e, "DLCI")
    r = _delete(client, e, "dlci")
    assert r.status_code == 200
    assert r.json()["deleted"] == "DLCI"


def test_delete_allows_readd(client):
    e = _email()
    _add_as(client, e, "RADD")
    _delete(client, e, "RADD")
    r = _add_as(client, e, "RADD")
    assert r.status_code == 200
