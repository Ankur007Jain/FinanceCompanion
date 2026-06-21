"""Tests for the /health endpoint."""


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_health_shape(client):
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["service"] == "FinanceCompanion API"
    assert "version" in data
    assert "db" in data
    assert "ai_configured" in data


def test_health_db_type_sqlite(client):
    data = client.get("/health").json()
    assert data["db"] == "sqlite"


def test_health_ai_configured(client):
    data = client.get("/health").json()
    # In test env ANTHROPIC_API_KEY=test-key so this should be True
    assert data["ai_configured"] is True
