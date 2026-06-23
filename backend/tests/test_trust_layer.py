"""
Tests for Phase 2 trust-layer fields — signal_convergence_score and convergence_details
stored and returned via ingest + analysis endpoints.
"""
import json
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

GOOD_SECRET = "test-job-secret"


def _mock_user(email: str = "trust@example.com"):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


def _ingest_with_trust(client, ticker: str, verdict: str = "BUY",
                       convergence_score: int = 6,
                       convergence_details: dict | None = None, **extra):
    details = convergence_details or {
        "oversold_rsi": True,
        "near_52w_low": True,
        "analyst_upside_15pct": True,
        "no_binary_risk": True,
        "positive_fcf": True,
        "institutional_backing": True,
        "price_stabilizing": False,
    }
    return client.post(
        "/jobs/ingest-analysis",
        params={"x_job_secret": GOOD_SECRET},
        json={
            "ticker": ticker,
            "analysis_date": str(date.today()),
            "verdict": verdict,
            "current_price": 150.0,
            "reasoning": "Trust layer test.",
            "signal_convergence_score": convergence_score,
            "convergence_details": json.dumps(details),
            **extra,
        },
    )


class TestConvergenceFieldsIngest:
    def test_ingest_accepts_convergence_score(self, client: TestClient):
        r = _ingest_with_trust(client, "CONV1", convergence_score=6)
        assert r.status_code == 200

    def test_ingest_without_convergence_score_accepted(self, client: TestClient):
        r = client.post(
            "/jobs/ingest-analysis",
            params={"x_job_secret": GOOD_SECRET},
            json={
                "ticker": "CONV2",
                "analysis_date": str(date.today()),
                "verdict": "WATCH",
                "current_price": 100.0,
            },
        )
        assert r.status_code == 200


class TestConvergenceFieldsReturned:
    def test_latest_returns_convergence_score(self, client: TestClient):
        _ingest_with_trust(client, "CVR1", convergence_score=5)
        with _mock_user():
            r = client.get("/analysis/CVR1/latest", params={"id_token": "fake"})
        assert r.status_code == 200
        assert r.json()["signal_convergence_score"] == 5

    def test_latest_returns_convergence_details_json(self, client: TestClient):
        details = {
            "oversold_rsi": True, "near_52w_low": False,
            "analyst_upside_15pct": True, "no_binary_risk": True,
            "positive_fcf": True, "institutional_backing": True,
            "price_stabilizing": True,
        }
        _ingest_with_trust(client, "CVR2", convergence_score=6,
                           convergence_details=details)
        with _mock_user():
            r = client.get("/analysis/CVR2/latest", params={"id_token": "fake"})
        data = r.json()
        assert data["convergence_details"] is not None
        parsed = json.loads(data["convergence_details"])
        assert parsed["oversold_rsi"] is True
        assert parsed["near_52w_low"] is False

    def test_digest_includes_convergence_fields(self, client: TestClient):
        _ingest_with_trust(client, "CVRD", verdict="BUY", convergence_score=7)
        with _mock_user("digest_trust@example.com"):
            client.post("/watchlist", params={"id_token": "fake"},
                        json={"ticker": "CVRD", "is_leveraged": False})
            r = client.get("/analysis/digest", params={"id_token": "fake"})
        items = r.json()
        assert items[0]["analysis"]["signal_convergence_score"] == 7

    def test_score_zero_when_not_ingested(self, client: TestClient):
        client.post(
            "/jobs/ingest-analysis",
            params={"x_job_secret": GOOD_SECRET},
            json={
                "ticker": "CZERO",
                "analysis_date": str(date.today()),
                "verdict": "WATCH",
                "current_price": 50.0,
            },
        )
        with _mock_user():
            r = client.get("/analysis/CZERO/latest", params={"id_token": "fake"})
        data = r.json()
        # Either null or 0 — both acceptable when not set
        assert data["signal_convergence_score"] in (None, 0)


class TestTrustLayerFields:
    def test_entry_quality_persisted(self, client: TestClient):
        _ingest_with_trust(client, "EQ1", verdict="BUY",
                           entry_quality="GREAT")
        with _mock_user():
            r = client.get("/analysis/EQ1/latest", params={"id_token": "fake"})
        assert r.json()["entry_quality"] == "GREAT"

    def test_hold_and_forget_rating_persisted(self, client: TestClient):
        _ingest_with_trust(client, "HF1", verdict="BUY",
                           hold_and_forget_rating="HOLD_AND_FORGET")
        with _mock_user():
            r = client.get("/analysis/HF1/latest", params={"id_token": "fake"})
        assert r.json()["hold_and_forget_rating"] == "HOLD_AND_FORGET"

    def test_position_size_pct_persisted(self, client: TestClient):
        _ingest_with_trust(client, "PS1", verdict="BUY",
                           position_size_pct="7-10%")
        with _mock_user():
            r = client.get("/analysis/PS1/latest", params={"id_token": "fake"})
        assert r.json()["position_size_pct"] == "7-10%"

    def test_scenarios_persisted_and_sum_to_100(self, client: TestClient):
        _ingest_with_trust(
            client, "SC1", verdict="BUY",
            scenario_bull="Strong revenue beat drives rerating.",
            scenario_base="Steady growth, multiple holds.",
            scenario_bear="Macro slowdown compresses margins.",
            scenario_bull_pct=35.0, scenario_base_pct=12.0, scenario_bear_pct=-18.0,
            scenario_bull_prob=30, scenario_base_prob=50, scenario_bear_prob=20,
        )
        with _mock_user():
            r = client.get("/analysis/SC1/latest", params={"id_token": "fake"})
        data = r.json()
        assert data["scenario_bull_pct"] == pytest.approx(35.0)
        assert data["scenario_base_pct"] == pytest.approx(12.0)
        assert data["scenario_bear_pct"] == pytest.approx(-18.0)
        total = data["scenario_bull_prob"] + data["scenario_base_prob"] + data["scenario_bear_prob"]
        assert total == 100

    def test_dont_panic_note_persisted(self, client: TestClient):
        _ingest_with_trust(client, "DP1", verdict="HOLD",
                           dont_panic_note="Price dropped 18% but thesis intact.")
        with _mock_user():
            r = client.get("/analysis/DP1/latest", params={"id_token": "fake"})
        assert "thesis intact" in r.json()["dont_panic_note"]

    def test_full_trust_layer_round_trip(self, client: TestClient):
        """All Phase 2 fields survive ingest → latest round trip."""
        details = {k: True for k in [
            "oversold_rsi", "near_52w_low", "analyst_upside_15pct",
            "no_binary_risk", "positive_fcf", "institutional_backing", "price_stabilizing"
        ]}
        _ingest_with_trust(
            client, "FULL1", verdict="BUY",
            convergence_score=7, convergence_details=details,
            entry_quality="GREAT", hold_and_forget_rating="HOLD_AND_FORGET",
            position_size_pct="8-10%",
            scenario_bull="Beats on every line.",
            scenario_base="Meets guidance.",
            scenario_bear="Misses on margins.",
            scenario_bull_pct=40.0, scenario_base_pct=10.0, scenario_bear_pct=-15.0,
            scenario_bull_prob=25, scenario_base_prob=55, scenario_bear_prob=20,
            dont_panic_note="",
        )
        with _mock_user():
            r = client.get("/analysis/FULL1/latest", params={"id_token": "fake"})
        data = r.json()
        assert data["signal_convergence_score"] == 7
        assert json.loads(data["convergence_details"])["oversold_rsi"] is True
        assert data["entry_quality"] == "GREAT"
        assert data["hold_and_forget_rating"] == "HOLD_AND_FORGET"
        assert data["position_size_pct"] == "8-10%"
        assert data["scenario_bull_pct"] == pytest.approx(40.0)
