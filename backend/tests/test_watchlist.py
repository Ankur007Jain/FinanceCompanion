"""Tests for POST /watchlist ticker validation."""
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
