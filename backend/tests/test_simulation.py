"""Tests for /simulation endpoints: portfolio, trades, copilot decide."""
import uuid
from unittest.mock import patch


def _email():
    return f"sim-{uuid.uuid4().hex[:8]}@example.com"


def _mock_user(email):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


def _portfolio(client, email, mode):
    with _mock_user(email):
        return client.get(f"/simulation/{mode}/portfolio", params={"id_token": "tok"})


def _trades(client, email, mode):
    with _mock_user(email):
        return client.get(f"/simulation/{mode}/trades", params={"id_token": "tok"})


def _decide(client, email, analysis_id, ticker, decision, **extra):
    with _mock_user(email):
        return client.post(
            "/simulation/copilot/decide",
            params={"id_token": "tok"},
            json={"analysis_id": analysis_id, "ticker": ticker, "decision": decision, **extra},
        )


# ── GET /{mode}/portfolio ────────────────────────────────────────────────────

def test_portfolio_empty_for_new_user(client):
    e = _email()
    r = _portfolio(client, e, "autopilot")
    assert r.status_code == 200
    assert r.json() == []


def test_portfolio_invalid_mode_returns_400(client):
    e = _email()
    r = _portfolio(client, e, "invalid")
    assert r.status_code == 400


def test_portfolio_copilot_mode_accepted(client):
    e = _email()
    r = _portfolio(client, e, "copilot")
    assert r.status_code == 200


def test_portfolio_unauthenticated_returns_401(client):
    r = client.get("/simulation/autopilot/portfolio", params={"id_token": "bad"})
    assert r.status_code == 401


# ── GET /{mode}/trades ───────────────────────────────────────────────────────

def test_trades_empty_for_new_user(client):
    e = _email()
    r = _trades(client, e, "autopilot")
    assert r.status_code == 200
    assert r.json() == []


def test_trades_invalid_mode_returns_400(client):
    e = _email()
    r = _trades(client, e, "badmode")
    assert r.status_code == 400


def test_trades_unauthenticated_returns_401(client):
    r = client.get("/simulation/copilot/trades", params={"id_token": "bad"})
    assert r.status_code == 401


# ── POST /copilot/decide ─────────────────────────────────────────────────────

def test_copilot_decide_approve(client):
    e = _email()
    r = _decide(client, e, "ana-001", "AAPL", "approve")
    assert r.status_code == 200
    assert r.json()["decision"] == "approve"


def test_copilot_decide_skip(client):
    e = _email()
    r = _decide(client, e, "ana-002", "TSLA", "skip")
    assert r.status_code == 200
    assert r.json()["status"] == "recorded"


def test_copilot_decide_override_with_fields(client):
    e = _email()
    r = _decide(client, e, "ana-003", "NVDA", "override",
                override_action="BUY", override_price=500.0)
    assert r.status_code == 200
    assert r.json()["decision"] == "override"


def test_copilot_decide_invalid_decision_returns_400(client):
    e = _email()
    r = _decide(client, e, "ana-004", "MSFT", "yolo")
    assert r.status_code == 400


def test_copilot_decide_ticker_uppercased(client):
    e = _email()
    r = _decide(client, e, "ana-005", "aapl", "approve")
    assert r.status_code == 200


def test_copilot_decide_unauthenticated_returns_401(client):
    r = client.post("/simulation/copilot/decide",
                    params={"id_token": "bad"},
                    json={"analysis_id": "x", "ticker": "AAPL", "decision": "approve"})
    assert r.status_code == 401
