"""
Tests for PATCH /auth/me — portfolio_size persistence and retrieval.
"""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


def _mock_user(email: str = "port@example.com"):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


class TestPortfolioPatch:
    def test_patch_me_saves_portfolio_size(self, client: TestClient):
        with _mock_user("p1@example.com"):
            r = client.patch(
                "/auth/me",
                params={"id_token": "fake"},
                json={"portfolio_size": 25000.0},
            )
        assert r.status_code == 200
        assert r.json()["portfolio_size"] == pytest.approx(25000.0)

    def test_patch_me_reflected_in_verify(self, client: TestClient):
        with _mock_user("p2@example.com"):
            client.patch("/auth/me", params={"id_token": "fake"},
                         json={"portfolio_size": 10000.0})
            r = client.post("/auth/verify", json={"id_token": "fake"})
        assert r.json()["portfolio_size"] == pytest.approx(10000.0)

    def test_patch_me_can_update_existing_value(self, client: TestClient):
        with _mock_user("p3@example.com"):
            client.patch("/auth/me", params={"id_token": "fake"},
                         json={"portfolio_size": 5000.0})
            r = client.patch("/auth/me", params={"id_token": "fake"},
                             json={"portfolio_size": 50000.0})
        assert r.json()["portfolio_size"] == pytest.approx(50000.0)

    def test_patch_me_empty_body_leaves_value_unchanged(self, client: TestClient):
        with _mock_user("p4@example.com"):
            client.patch("/auth/me", params={"id_token": "fake"},
                         json={"portfolio_size": 15000.0})
            r = client.patch("/auth/me", params={"id_token": "fake"}, json={})
        assert r.json()["portfolio_size"] == pytest.approx(15000.0)

    def test_patch_me_unauthenticated_returns_401(self, client: TestClient):
        r = client.patch("/auth/me", params={"id_token": "bad-token"},
                         json={"portfolio_size": 1000.0})
        assert r.status_code == 401

    def test_patch_me_portfolio_size_null_by_default(self, client: TestClient):
        with _mock_user("p5_new@example.com"):
            r = client.post("/auth/verify", json={"id_token": "fake"})
        assert r.json()["portfolio_size"] is None

    def test_patch_me_fractional_value_accepted(self, client: TestClient):
        with _mock_user("p6@example.com"):
            r = client.patch("/auth/me", params={"id_token": "fake"},
                             json={"portfolio_size": 12345.67})
        assert r.json()["portfolio_size"] == pytest.approx(12345.67)

    def test_patch_me_returns_full_user_shape(self, client: TestClient):
        with _mock_user("p7@example.com"):
            r = client.patch("/auth/me", params={"id_token": "fake"},
                             json={"portfolio_size": 20000.0})
        data = r.json()
        assert "email" in data
        assert "tier" in data
        assert "tokens_used" in data
        assert "portfolio_size" in data

    def test_patch_me_is_user_scoped(self, client: TestClient):
        with _mock_user("pA@example.com"):
            client.patch("/auth/me", params={"id_token": "fake"},
                         json={"portfolio_size": 99999.0})
        with _mock_user("pB@example.com"):
            r = client.post("/auth/verify", json={"id_token": "fake"})
        assert r.json()["portfolio_size"] is None
