"""
Integration test for POST /jobs/price-series — the endpoint scripts/nightly_fetch.py
calls instead of pulling yfinance history directly. sync_and_get_bars itself is unit
tested in test_price_history_sync.py; this only verifies the endpoint's auth guard and
that it wires the ticker through correctly (monkeypatched to avoid a live yfinance call).
"""
import routers.jobs as jobs_router

JOB_SECRET = "test-job-secret"


class TestPriceSeriesEndpoint:
    def test_rejects_wrong_job_secret(self, client):
        r = client.post("/jobs/price-series", params={"ticker": "AAPL", "x_job_secret": "wrong"})
        assert r.status_code == 401

    def test_returns_symbol_and_bars(self, client, monkeypatch):
        monkeypatch.setattr(
            jobs_router, "sync_and_get_bars",
            lambda ticker, db: [{"date": "2026-06-01", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100}],
        )

        r = client.post("/jobs/price-series", params={"ticker": "AAPL", "x_job_secret": JOB_SECRET})

        assert r.status_code == 200
        body = r.json()
        assert body["symbol"] == "AAPL"
        assert body["bars"] == [{"date": "2026-06-01", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100}]
