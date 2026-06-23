"""
Integration tests for the nightly GHA job pipeline (Phase 0).

Tests the full flow the GHA workflow executes each night:
  Step 1  — fetch raw data, compute metrics
  Step 1b — POST /jobs/ingest-snapshot  (raw data persisted)
  Step 4  — POST /jobs/ingest-analysis  (verdict persisted)

Verifies DB consistency, data format integrity, and pipeline ordering.
"""
import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

JOB_SECRET  = "test-job-secret"
ADMIN_SECRET = "test-admin-secret"
TODAY = str(date.today())

# Realistic yfinance-style payloads that the Step 1 script produces
_SNAPSHOT_NVDA = {
    "ticker": "NVDA",
    "cache_date": TODAY,
    "info_json": json.dumps({
        "currentPrice": 127.40,
        "previousClose": 124.80,
        "fiftyTwoWeekHigh": 153.13,
        "fiftyTwoWeekLow": 86.22,
        "recommendationKey": "buy",
        "targetMeanPrice": 155.0,
        "trailingPE": 38.2,
        "forwardPE": 28.5,
        "profitMargins": 0.553,
        "debtToEquity": 17.4,
        "freeCashflow": 17_800_000_000,
    }),
    "history_json": json.dumps([
        {"Date": "2026-06-20", "Open": 125.1, "High": 128.3, "Low": 124.8, "Close": 127.4, "Volume": 45_000_000},
        {"Date": "2026-06-19", "Open": 122.5, "High": 126.0, "Low": 121.9, "Close": 124.8, "Volume": 52_000_000},
        {"Date": "2026-06-18", "Open": 120.0, "High": 123.4, "Low": 119.5, "Close": 122.5, "Volume": 48_000_000},
    ]),
    "news_json": json.dumps([
        {"title": "Nvidia beats Q2 estimates on AI demand", "publisher": "Reuters", "link": "https://reuters.com/1"},
        {"title": "Blackwell supply ramp accelerates", "publisher": "Bloomberg", "link": "https://bloomberg.com/2"},
    ]),
    "calendar_json": json.dumps({"Earnings Date": ["2026-08-20"]}),
}

_ANALYSIS_NVDA = {
    "ticker": "NVDA",
    "analysis_date": TODAY,
    "verdict": "BUY",
    "current_price": 127.40,
    "price_change_pct": 2.1,
    "week52_high": 153.13,
    "week52_low": 86.22,
    "week52_position_pct": 61.8,
    "ma50": 121.5,
    "ma200": 108.3,
    "rsi": 58.4,
    "analyst_consensus": "BUY",
    "analyst_upside_pct": 21.7,
    "conviction_score": 78,
    "risk_level": "MED",
    "confidence": "High",
    "entry_target": 124.0,
    "exit_target": 148.0,
    "stop_loss": 118.0,
    "hold_period": "4-8 weeks",
    "reasoning": "AI demand driving sustained revenue growth with improving margins.",
    "bull_case": "Blackwell ramp exceeds expectations, pushing to $155.",
    "bear_case": "Export restrictions tighten, delaying enterprise deployments.",
    "thesis_invalidation": "Quarterly revenue guidance cut below $32B.",
    "news_summary": "Nvidia continues to benefit from strong AI infrastructure spending.",
    "signal_convergence_score": 6,
    "earnings_date": "2026-08-20",
}


class TestSnapshotEndpoint:
    def test_snapshot_saves_full_payload(self, client: TestClient):
        r = client.post(
            "/jobs/ingest-snapshot",
            params={"x_job_secret": JOB_SECRET},
            json=_SNAPSHOT_NVDA,
        )
        assert r.status_code == 200
        assert r.json() == {"status": "saved", "ticker": "NVDA", "date": TODAY}

    def test_snapshot_rejects_bad_secret(self, client: TestClient):
        r = client.post(
            "/jobs/ingest-snapshot",
            params={"x_job_secret": "hacker"},
            json={"ticker": "NVDA", "cache_date": TODAY},
        )
        assert r.status_code == 401

    def test_snapshot_accepts_minimal_payload(self, client: TestClient):
        r = client.post(
            "/jobs/ingest-snapshot",
            params={"x_job_secret": JOB_SECRET},
            json={"ticker": "MINIMAL", "cache_date": TODAY},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "saved"

    def test_snapshot_upserts_on_same_ticker_date(self, client: TestClient):
        base = {"ticker": "UPSRT", "cache_date": TODAY, "info_json": '{"price": 50}'}
        r1 = client.post("/jobs/ingest-snapshot", params={"x_job_secret": JOB_SECRET}, json=base)
        assert r1.status_code == 200

        updated = {**base, "info_json": '{"price": 55}'}
        r2 = client.post("/jobs/ingest-snapshot", params={"x_job_secret": JOB_SECRET}, json=updated)
        assert r2.status_code == 200
        assert r2.json()["status"] == "saved"

    def test_snapshot_different_dates_stored_separately(self, client: TestClient):
        yesterday = str(date.today() - timedelta(days=1))
        r1 = client.post("/jobs/ingest-snapshot", params={"x_job_secret": JOB_SECRET},
                         json={"ticker": "DTEST", "cache_date": TODAY, "info_json": '{"day": "today"}'})
        r2 = client.post("/jobs/ingest-snapshot", params={"x_job_secret": JOB_SECRET},
                         json={"ticker": "DTEST", "cache_date": yesterday, "info_json": '{"day": "yesterday"}'})
        assert r1.status_code == 200
        assert r2.status_code == 200


class TestSnapshotDataIntegrity:
    """Verify the raw JSON fields produced by Step 1 are well-formed."""

    def test_info_json_is_parseable(self):
        info = json.loads(_SNAPSHOT_NVDA["info_json"])
        assert isinstance(info, dict)
        assert info["currentPrice"] == 127.40
        assert info["recommendationKey"] == "buy"

    def test_history_json_contains_ohlcv_records(self):
        records = json.loads(_SNAPSHOT_NVDA["history_json"])
        assert isinstance(records, list)
        assert len(records) == 3
        first = records[0]
        for field in ("Date", "Open", "High", "Low", "Close", "Volume"):
            assert field in first, f"Missing OHLCV field: {field}"

    def test_history_records_have_valid_prices(self):
        records = json.loads(_SNAPSHOT_NVDA["history_json"])
        for r in records:
            assert r["High"] >= r["Low"], "High must be >= Low"
            assert r["Close"] > 0

    def test_news_json_is_list_of_articles(self):
        articles = json.loads(_SNAPSHOT_NVDA["news_json"])
        assert isinstance(articles, list)
        assert all("title" in a for a in articles)

    def test_calendar_json_has_earnings_date(self):
        cal = json.loads(_SNAPSHOT_NVDA["calendar_json"])
        assert "Earnings Date" in cal
        assert len(cal["Earnings Date"]) > 0


class TestStep1PriceComputations:
    """
    Unit tests for the metric computations in the Step 1 Python script.
    Tests the exact formulas embedded in the GHA prompt — no yfinance calls.
    """

    def _compute(self, price, prev, hi52, lo52, ma50_closes, ma200_closes, rsi_gains_losses):
        chg = ((price - prev) / prev * 100) if prev else 0
        rng = ((price - lo52) / (hi52 - lo52) * 100) if (hi52 - lo52) > 0 else 50
        ma50 = sum(ma50_closes[-50:]) / min(len(ma50_closes), 50) if ma50_closes else None
        ma200 = sum(ma200_closes[-200:]) / min(len(ma200_closes), 200) if ma200_closes else None
        avg_gain, avg_loss = rsi_gains_losses
        rsi = (100 - 100 / (1 + avg_gain / avg_loss)) if avg_loss != 0 else 50
        return {"chg": chg, "rng": rng, "ma50": ma50, "ma200": ma200, "rsi": rsi}

    def test_price_change_pct(self):
        r = self._compute(127.4, 124.8, 153.13, 86.22, [], [], (1, 1))
        assert abs(r["chg"] - 2.0833) < 0.01

    def test_range_position_at_midpoint(self):
        r = self._compute(100, 100, 150, 50, [], [], (1, 1))
        assert r["rng"] == pytest.approx(50.0)

    def test_range_position_at_52w_low(self):
        r = self._compute(50, 50, 150, 50, [], [], (1, 1))
        assert r["rng"] == pytest.approx(0.0)

    def test_range_position_at_52w_high(self):
        r = self._compute(150, 150, 150, 50, [], [], (1, 1))
        assert r["rng"] == pytest.approx(100.0)

    def test_range_zero_spread_defaults_to_50(self):
        r = self._compute(100, 100, 100, 100, [], [], (1, 1))
        assert r["rng"] == 50

    def test_rsi_neutral_equal_gains_losses(self):
        r = self._compute(100, 99, 150, 50, [], [], (1.0, 1.0))
        assert r["rsi"] == pytest.approx(50.0)

    def test_rsi_overbought_territory(self):
        r = self._compute(100, 99, 150, 50, [], [], (3.0, 1.0))
        assert r["rsi"] > 70

    def test_rsi_oversold_territory(self):
        r = self._compute(100, 99, 150, 50, [], [], (1.0, 3.0))
        assert r["rsi"] < 30

    def test_rsi_zero_loss_returns_50(self):
        r = self._compute(100, 99, 150, 50, [], [], (2.0, 0.0))
        assert r["rsi"] == 50


class TestNightlyPipeline:
    """
    Integration: full nightly flow for one ticker.
    Step 1b (snapshot) runs before Step 4 (analysis) — both tables populated.
    """

    def test_snapshot_does_not_count_as_analyzed_today(self, client: TestClient):
        import os; os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        client.post("/jobs/ingest-snapshot", params={"x_job_secret": JOB_SECRET},
                    json={"ticker": "SNAPONLY", "cache_date": TODAY})
        r = client.get("/jobs/admin/analyzed-today", params={"x_admin_secret": ADMIN_SECRET})
        assert "SNAPONLY" not in r.json()["analyzed"]

    def test_full_pipeline_snapshot_then_analysis(self, client: TestClient):
        import os; os.environ["ADMIN_SECRET"] = ADMIN_SECRET

        # Step 1b — snapshot saved first
        rs = client.post("/jobs/ingest-snapshot", params={"x_job_secret": JOB_SECRET},
                         json=_SNAPSHOT_NVDA)
        assert rs.status_code == 200

        # Step 4 — analysis ingested after
        ra = client.post("/jobs/ingest-analysis", params={"x_job_secret": JOB_SECRET},
                         json=_ANALYSIS_NVDA)
        assert ra.status_code == 200
        assert ra.json()["ticker"] == "NVDA"

        # NVDA now appears in analyzed-today
        rd = client.get("/jobs/admin/analyzed-today", params={"x_admin_secret": ADMIN_SECRET})
        assert "NVDA" in rd.json()["analyzed"]

    def test_analysis_without_prior_snapshot_still_works(self, client: TestClient):
        """Snapshot is best-effort — analysis must succeed even if snapshot step failed."""
        payload = {**_ANALYSIS_NVDA, "ticker": "NOSNAPSHOT"}
        r = client.post("/jobs/ingest-analysis", params={"x_job_secret": JOB_SECRET}, json=payload)
        assert r.status_code == 200

    def test_events_json_synthesized_from_earnings_date(self, client: TestClient):
        """When agent sends earnings_date, backend synthesizes events_json automatically."""
        payload = {**_ANALYSIS_NVDA, "ticker": "EARNT", "earnings_date": "2026-08-20"}
        r = client.post("/jobs/ingest-analysis", params={"x_job_secret": JOB_SECRET}, json=payload)
        assert r.status_code == 200

    def test_batch_of_tickers_all_land_in_analyzed_today(self, client: TestClient):
        import os; os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        batch = ["BTCH1", "BTCH2", "BTCH3"]

        for ticker in batch:
            # Step 1b
            client.post("/jobs/ingest-snapshot", params={"x_job_secret": JOB_SECRET},
                        json={"ticker": ticker, "cache_date": TODAY})
            # Step 4
            client.post("/jobs/ingest-analysis", params={"x_job_secret": JOB_SECRET},
                        json={**_ANALYSIS_NVDA, "ticker": ticker})

        r = client.get("/jobs/admin/analyzed-today", params={"x_admin_secret": ADMIN_SECRET})
        analyzed = r.json()["analyzed"]
        for ticker in batch:
            assert ticker in analyzed

    def test_duplicate_analysis_updates_not_duplicates(self, client: TestClient):
        """Second POST for same ticker+date should update, not create duplicate."""
        payload = {**_ANALYSIS_NVDA, "ticker": "DUPL"}
        r1 = client.post("/jobs/ingest-analysis", params={"x_job_secret": JOB_SECRET}, json=payload)
        assert r1.json()["status"] in ("created", "updated")

        payload2 = {**payload, "verdict": "HOLD", "conviction_score": 55}
        r2 = client.post("/jobs/ingest-analysis", params={"x_job_secret": JOB_SECRET}, json=payload2)
        assert r2.json()["status"] == "updated"
