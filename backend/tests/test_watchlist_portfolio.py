"""
Tests for the new portfolio PATCH endpoints on the watchlist router:
  - PATCH /watchlist/{ticker}/portfolio  — set shares + avg_cost
  - PATCH /watchlist/{ticker}/sell       — clear shares/avg_cost (return to watchlist view)
Also verifies that shares/avg_cost flow through the digest endpoint correctly.
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _mock_user(email: str = "port@example.com"):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


def _uid():
    return f"wlp-{uuid.uuid4().hex[:8]}@example.com"


def _add_watchlist(client, email: str, ticker: str):
    with _mock_user(email), patch("routers.watchlist._detect_leveraged", return_value=False):
        r = client.post(
            "/watchlist",
            params={"id_token": "tok"},
            json={"ticker": ticker, "company_name": "Test Co"},
        )
    assert r.status_code == 200, r.json()
    return r.json()


def _set_position(client, email: str, ticker: str, shares: float, avg_cost: float | None = None):
    body: dict = {"shares": shares}
    if avg_cost is not None:
        body["avg_cost"] = avg_cost
    with _mock_user(email):
        return client.patch(
            f"/watchlist/{ticker}/portfolio",
            params={"id_token": "tok"},
            json=body,
        )


def _sell(client, email: str, ticker: str):
    with _mock_user(email):
        return client.patch(f"/watchlist/{ticker}/sell", params={"id_token": "tok"})


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /watchlist/{ticker}/portfolio
# ══════════════════════════════════════════════════════════════════════════════

class TestSetPortfolioPosition:
    def test_set_shares_returns_200(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SPOSA")
        r = _set_position(client, email, "SPOSA", 10.0)
        assert r.status_code == 200

    def test_response_includes_shares(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SPOSB")
        r = _set_position(client, email, "SPOSB", 7.5)
        assert r.json()["shares"] == pytest.approx(7.5)

    def test_response_includes_avg_cost(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SPOSC")
        r = _set_position(client, email, "SPOSC", 5.0, avg_cost=200.0)
        assert r.json()["avg_cost"] == pytest.approx(200.0)

    def test_avg_cost_optional(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SPOSD")
        r = _set_position(client, email, "SPOSD", 3.0)
        assert r.status_code == 200
        assert r.json()["avg_cost"] is None

    def test_fractional_shares_accepted(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SPOSE")
        r = _set_position(client, email, "SPOSE", 0.123456)
        assert r.json()["shares"] == pytest.approx(0.123456)

    def test_ticker_not_in_watchlist_returns_404(self, client: TestClient):
        email = _uid()
        r = _set_position(client, email, "NOTHERE", 5.0)
        assert r.status_code == 404

    def test_unauthenticated_returns_401(self, client: TestClient):
        r = client.patch(
            "/watchlist/AAPL/portfolio",
            params={"id_token": "bad-token"},
            json={"shares": 5.0},
        )
        assert r.status_code == 401

    def test_ticker_case_insensitive(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SPCI")
        r = _set_position(client, email, "spci", 3.0)
        assert r.status_code == 200
        assert r.json()["ticker"] == "SPCI"

    def test_updates_existing_position(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SPUP")
        _set_position(client, email, "SPUP", 5.0, avg_cost=100.0)
        r = _set_position(client, email, "SPUP", 15.0, avg_cost=120.0)
        assert r.json()["shares"] == pytest.approx(15.0)
        assert r.json()["avg_cost"] == pytest.approx(120.0)

    def test_user_isolation(self, client: TestClient):
        emailA, emailB = _uid(), _uid()
        _add_watchlist(client, emailA, "SPISO")
        # User B cannot set position on User A's item
        r = _set_position(client, emailB, "SPISO", 5.0)
        assert r.status_code == 404

    def test_shares_missing_returns_422(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SPVAL")
        with _mock_user(email):
            r = client.patch(
                "/watchlist/SPVAL/portfolio",
                params={"id_token": "tok"},
                json={"avg_cost": 100.0},  # shares omitted
            )
        assert r.status_code == 422

    def test_shares_persisted_after_set(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SPRS")
        _set_position(client, email, "SPRS", 20.0, avg_cost=175.0)
        with _mock_user(email):
            r = client.get("/watchlist", params={"id_token": "tok"})
        items = {i["ticker"]: i for i in r.json()}
        assert items["SPRS"]["shares"] == pytest.approx(20.0)
        assert items["SPRS"]["avg_cost"] == pytest.approx(175.0)


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /watchlist/{ticker}/sell
# ══════════════════════════════════════════════════════════════════════════════

class TestClearPortfolioPosition:
    def test_sell_returns_200(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SELLA")
        _set_position(client, email, "SELLA", 10.0)
        r = _sell(client, email, "SELLA")
        assert r.status_code == 200

    def test_sell_clears_shares(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SELLB")
        _set_position(client, email, "SELLB", 10.0)
        r = _sell(client, email, "SELLB")
        assert r.json()["shares"] is None

    def test_sell_clears_avg_cost(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SELLC")
        _set_position(client, email, "SELLC", 10.0, avg_cost=150.0)
        r = _sell(client, email, "SELLC")
        assert r.json()["avg_cost"] is None

    def test_sell_keeps_item_in_watchlist(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SELLD")
        _set_position(client, email, "SELLD", 5.0)
        _sell(client, email, "SELLD")
        with _mock_user(email):
            r = client.get("/watchlist", params={"id_token": "tok"})
        tickers = [i["ticker"] for i in r.json()]
        assert "SELLD" in tickers

    def test_sell_not_in_watchlist_returns_404(self, client: TestClient):
        email = _uid()
        r = _sell(client, email, "GHOSTTK")
        assert r.status_code == 404

    def test_unauthenticated_returns_401(self, client: TestClient):
        r = client.patch("/watchlist/AAPL/sell", params={"id_token": "bad-token"})
        assert r.status_code == 401

    def test_sell_ticker_case_insensitive(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "SLCI")
        _set_position(client, email, "SLCI", 5.0)
        r = _sell(client, email, "slci")
        assert r.status_code == 200
        assert r.json()["ticker"] == "SLCI"

    def test_sell_user_isolation(self, client: TestClient):
        emailA, emailB = _uid(), _uid()
        _add_watchlist(client, emailA, "SLISO")
        _set_position(client, emailA, "SLISO", 5.0)
        r = _sell(client, emailB, "SLISO")
        assert r.status_code == 404

    def test_sell_on_watchlist_only_item_clears_nulls(self, client: TestClient):
        # Item that never had shares — sell should still return 200 with null fields
        email = _uid()
        _add_watchlist(client, email, "SLNV")
        r = _sell(client, email, "SLNV")
        assert r.status_code == 200
        assert r.json()["shares"] is None
        assert r.json()["avg_cost"] is None

    def test_can_set_position_again_after_sell(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "READD")
        _set_position(client, email, "READD", 5.0)
        _sell(client, email, "READD")
        r = _set_position(client, email, "READD", 10.0, avg_cost=200.0)
        assert r.status_code == 200
        assert r.json()["shares"] == pytest.approx(10.0)


# ══════════════════════════════════════════════════════════════════════════════
# Digest — shares/avg_cost propagation
# ══════════════════════════════════════════════════════════════════════════════

class TestDigestPortfolioFields:
    def test_digest_item_has_shares_field(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "DGTSA")
        with _mock_user(email):
            r = client.get("/analysis/digest", params={"id_token": "tok"})
        item = next(i for i in r.json() if i["ticker"] == "DGTSA")
        assert "shares" in item

    def test_digest_item_shares_null_for_watchlist_only(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "DGTSB")
        with _mock_user(email):
            r = client.get("/analysis/digest", params={"id_token": "tok"})
        item = next(i for i in r.json() if i["ticker"] == "DGTSB")
        assert item["shares"] is None
        assert item["avg_cost"] is None

    def test_digest_item_shares_set_after_portfolio_position(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "DGTSC")
        _set_position(client, email, "DGTSC", 8.0, avg_cost=180.0)
        with _mock_user(email):
            r = client.get("/analysis/digest", params={"id_token": "tok"})
        item = next(i for i in r.json() if i["ticker"] == "DGTSC")
        assert item["shares"] == pytest.approx(8.0)
        assert item["avg_cost"] == pytest.approx(180.0)

    def test_digest_item_shares_cleared_after_sell(self, client: TestClient):
        email = _uid()
        _add_watchlist(client, email, "DGTSD")
        _set_position(client, email, "DGTSD", 8.0)
        _sell(client, email, "DGTSD")
        with _mock_user(email):
            r = client.get("/analysis/digest", params={"id_token": "tok"})
        item = next(i for i in r.json() if i["ticker"] == "DGTSD")
        assert item["shares"] is None
