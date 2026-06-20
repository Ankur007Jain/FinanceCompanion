"""
API tests — uses TestClient with SQLite override.
Anthropic and Google token calls are mocked.
"""
import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _mock_google_token(email: str = "test@example.com"):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test User"},
    )


@contextmanager
def _mock_anthropic_stream(text: str = "HOLD — test verdict."):
    chunk = MagicMock()
    chunk.type = "content_block_delta"
    chunk.delta = MagicMock()
    chunk.delta.type = "text_delta"
    chunk.delta.text = text

    final_msg = MagicMock()
    final_msg.stop_reason = "end_turn"
    final_msg.usage = MagicMock(
        input_tokens=10, output_tokens=20,
        cache_read_input_tokens=0, cache_creation_input_tokens=0,
    )
    final_msg.content = []

    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = MagicMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = MagicMock(return_value=False)

    async def _aiter():
        yield chunk

    stream_ctx.__aiter__ = _aiter
    stream_ctx.get_final_message = MagicMock(return_value=final_msg)

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = stream_ctx

    with patch("routers.streaming.anthropic.AsyncAnthropic", return_value=mock_client):
        yield


class TestHealth:
    def test_health(self, client: TestClient):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_jobs_health(self, client: TestClient):
        r = client.get("/jobs/health")
        assert r.status_code == 200


class TestAuth:
    def test_verify_token(self, client: TestClient):
        with _mock_google_token():
            r = client.post("/auth/verify", json={"id_token": "fake-token"})
        assert r.status_code == 200
        assert r.json()["email"] == "test@example.com"

    def test_verify_bad_token(self, client: TestClient):
        r = client.post("/auth/verify", json={"id_token": "bad"})
        assert r.status_code == 401


class TestWatchlist:
    def test_empty_watchlist(self, client: TestClient):
        with _mock_google_token():
            r = client.get("/watchlist", params={"id_token": "fake"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_add_and_remove(self, client: TestClient):
        with _mock_google_token():
            r = client.post(
                "/watchlist",
                params={"id_token": "fake"},
                json={"ticker": "NFLX", "company_name": "Netflix", "is_leveraged": False},
            )
        assert r.status_code == 200
        assert r.json()["ticker"] == "NFLX"

        with _mock_google_token():
            r2 = client.delete("/watchlist/NFLX", params={"id_token": "fake"})
        assert r2.status_code == 200

    def test_duplicate_add(self, client: TestClient):
        with _mock_google_token("dup@example.com"):
            client.post("/watchlist", params={"id_token": "fake"},
                        json={"ticker": "AAPL", "is_leveraged": False})
            r = client.post("/watchlist", params={"id_token": "fake"},
                            json={"ticker": "AAPL", "is_leveraged": False})
        assert r.status_code == 409


class TestAnalysis:
    def test_digest_empty(self, client: TestClient):
        with _mock_google_token("digest@example.com"):
            r = client.get("/analysis/digest", params={"id_token": "fake"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_history_unknown_ticker(self, client: TestClient):
        with _mock_google_token():
            r = client.get("/analysis/FAKEXYZ/history", params={"id_token": "fake"})
        assert r.status_code == 200
        assert r.json() == []


class TestConversations:
    def test_create_and_list(self, client: TestClient):
        with _mock_google_token("conv@example.com"):
            r = client.post("/conversations", params={"id_token": "fake"},
                            json={"ticker": "NFLX", "title": "Netflix analysis"})
        assert r.status_code == 200
        conv_id = r.json()["id"]

        with _mock_google_token("conv@example.com"):
            r2 = client.get("/conversations", params={"id_token": "fake"})
        assert r2.status_code == 200
        ids = [c["id"] for c in r2.json()]
        assert conv_id in ids

    def test_delete_conversation(self, client: TestClient):
        with _mock_google_token("del@example.com"):
            r = client.post("/conversations", params={"id_token": "fake"}, json={})
        conv_id = r.json()["id"]
        with _mock_google_token("del@example.com"):
            r2 = client.delete(f"/conversations/{conv_id}", params={"id_token": "fake"})
        assert r2.status_code == 200


class TestJobs:
    def test_nightly_bad_secret(self, client: TestClient):
        r = client.post("/jobs/nightly", json={"secret": "wrong", "tickers": ["NFLX"]})
        assert r.status_code == 401

    def test_nightly_good_secret(self, client: TestClient):
        r = client.post("/jobs/nightly", json={"secret": "test-job-secret", "tickers": ["NFLX"]})
        assert r.status_code == 200
