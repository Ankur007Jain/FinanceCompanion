"""Tests for /conversations endpoints."""
import uuid
from unittest.mock import patch


def _email():
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


def _mock_user(email):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


def _create(client, email, ticker=None, title="Chat"):
    with _mock_user(email):
        return client.post(
            "/conversations",
            params={"id_token": "tok"},
            json={"ticker": ticker, "title": title},
        )


def test_create_returns_200(client):
    e = _email()
    assert _create(client, e).status_code == 200


def test_create_ticker_normalized(client):
    e = _email()
    assert _create(client, e, ticker="aapl").json()["ticker"] == "AAPL"


def test_create_no_ticker(client):
    e = _email()
    assert _create(client, e, ticker=None).json()["ticker"] is None


def test_list_empty(client):
    e = _email()
    with _mock_user(e):
        r = client.get("/conversations", params={"id_token": "tok"})
    assert r.status_code == 200
    assert r.json() == []


def test_list_returns_created(client):
    e = _email()
    _create(client, e, ticker="TSLA", title="Tesla chat")
    with _mock_user(e):
        r = client.get("/conversations", params={"id_token": "tok"})
    assert len(r.json()) == 1
    assert r.json()[0]["title"] == "Tesla chat"


def test_get_by_ticker_returns_matching(client):
    e = _email()
    _create(client, e, ticker="NVDA", title="Nvidia chat")
    _create(client, e, ticker="AAPL", title="Apple chat")
    with _mock_user(e):
        r = client.get("/conversations/by-ticker/NVDA", params={"id_token": "tok"})
    assert r.status_code == 200
    convs = r.json()
    assert len(convs) == 1
    assert convs[0]["ticker"] == "NVDA"


def test_get_by_ticker_case_insensitive(client):
    e = _email()
    _create(client, e, ticker="MSFT", title="Microsoft chat")
    with _mock_user(e):
        r = client.get("/conversations/by-ticker/msft", params={"id_token": "tok"})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_by_ticker_empty_when_none(client):
    e = _email()
    _create(client, e, ticker="GOOG")
    with _mock_user(e):
        r = client.get("/conversations/by-ticker/TSLA", params={"id_token": "tok"})
    assert r.json() == []


def test_get_404_wrong_user(client):
    e1, e2 = _email(), _email()
    conv_id = _create(client, e1, title="Mine").json()["id"]
    with _mock_user(e2):
        r = client.get(f"/conversations/{conv_id}", params={"id_token": "tok"})
    assert r.status_code == 404


def test_delete_conversation(client):
    e = _email()
    conv_id = _create(client, e, title="Delete me").json()["id"]
    with _mock_user(e):
        assert client.delete(f"/conversations/{conv_id}", params={"id_token": "tok"}).status_code == 200
        assert client.get(f"/conversations/{conv_id}", params={"id_token": "tok"}).status_code == 404
