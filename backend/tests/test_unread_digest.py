"""Tests for unread tracking fields in GET /analysis/digest and _change_summary()."""
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


GOOD_SECRET = "test-job-secret"


def _mock_user(email: str = "user@example.com"):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


def _email():
    return f"ud-{uuid.uuid4().hex[:8]}@example.com"


def _add(client, email, ticker):
    with _mock_user(email), patch("routers.watchlist._detect_leveraged", return_value=False):
        return client.post(
            "/watchlist",
            params={"id_token": "tok"},
            json={"ticker": ticker, "company_name": "Test Co", "sector": "Tech"},
        )


def _ingest(client, ticker, verdict="HOLD", analysis_date=None, **extra):
    return client.post(
        "/jobs/ingest-analysis",
        params={"x_job_secret": GOOD_SECRET},
        json={
            "ticker": ticker,
            "analysis_date": analysis_date or str(date.today()),
            "verdict": verdict,
            "current_price": 100.0,
            "reasoning": "Test.",
            **extra,
        },
    )


def _digest(client, email):
    with _mock_user(email):
        return client.get("/analysis/digest", params={"id_token": "tok"})


def _mark_read(client, email, ticker):
    with _mock_user(email):
        return client.patch(f"/watchlist/{ticker}/read", params={"id_token": "tok"})


class TestDigestUnreadFields:
    def test_digest_item_has_unread_fields(self, client: TestClient):
        e = _email()
        _add(client, e, "UDFT")
        _ingest(client, "UDFT")
        r = _digest(client, e)
        assert r.status_code == 200
        item = r.json()[0]
        assert "has_unread" in item
        assert "change_summary" in item
        assert "days_since_read" in item

    def test_never_read_has_unread_true(self, client: TestClient):
        e = _email()
        _add(client, e, "UDNR")
        _ingest(client, "UDNR")
        item = _digest(client, e).json()[0]
        assert item["has_unread"] is True
        assert item["change_summary"] == "New analysis available"

    def test_no_analysis_has_unread_false(self, client: TestClient):
        e = _email()
        _add(client, e, "UDNO")
        item = _digest(client, e).json()[0]
        assert item["has_unread"] is False
        assert item["change_summary"] is None

    def test_already_read_same_analysis_has_unread_false(self, client: TestClient):
        e = _email()
        _add(client, e, "UDAR")
        _ingest(client, "UDAR")
        _mark_read(client, e, "UDAR")
        item = _digest(client, e).json()[0]
        assert item["has_unread"] is False
        assert item["change_summary"] is None

    def test_new_analysis_after_read_verdict_flip_has_unread(self, client: TestClient):
        e = _email()
        yesterday = str(date.today() - timedelta(days=1))
        _add(client, e, "UDVF")
        _ingest(client, "UDVF", verdict="BUY", analysis_date=yesterday)
        _mark_read(client, e, "UDVF")
        _ingest(client, "UDVF", verdict="SELL")
        item = _digest(client, e).json()[0]
        assert item["has_unread"] is True
        assert "BUY" in item["change_summary"] or "SELL" in item["change_summary"]

    def test_new_analysis_with_no_meaningful_change_has_unread_false(self, client: TestClient):
        e = _email()
        yesterday = str(date.today() - timedelta(days=1))
        _add(client, e, "UDNC")
        _ingest(client, "UDNC", verdict="HOLD",
                conviction_score=70, rsi=50.0, analysis_date=yesterday)
        _mark_read(client, e, "UDNC")
        # Same verdict, same conviction, same RSI, no news, no conflicts, same signals
        _ingest(client, "UDNC", verdict="HOLD",
                conviction_score=71, rsi=51.0)
        item = _digest(client, e).json()[0]
        assert item["has_unread"] is False
        assert item["change_summary"] is None

    def test_days_since_read_is_none_for_never_read(self, client: TestClient):
        e = _email()
        _add(client, e, "UDDS")
        _ingest(client, "UDDS")
        item = _digest(client, e).json()[0]
        # Never-read → days_since_read is None (no last_read_at)
        assert item["days_since_read"] is None

    def test_days_since_read_set_after_read(self, client: TestClient):
        e = _email()
        yesterday = str(date.today() - timedelta(days=1))
        _add(client, e, "UDDR")
        _ingest(client, "UDDR", verdict="BUY", analysis_date=yesterday)
        _mark_read(client, e, "UDDR")
        _ingest(client, "UDDR", verdict="SELL")
        item = _digest(client, e).json()[0]
        # was read today → 0 days
        assert item["days_since_read"] is not None
        assert item["days_since_read"] >= 0


class TestChangeSummary:
    """Unit tests for _change_summary() — each of the 7 signal triggers."""

    def _make_analysis(self, **kwargs):
        from types import SimpleNamespace
        defaults = dict(
            id="test-id",
            ticker="TEST",
            analysis_date=date.today(),
            verdict="HOLD",
            is_important_day=False,
            conviction_score=70,
            rsi=50.0,
            news_summary=None,
            data_conflicts=None,
            signal_convergence_score=5,
        )
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_verdict_flip_detected(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(verdict="BUY")
        prev = self._make_analysis(verdict="SELL")
        changed, summary = _change_summary(cur, prev)
        assert changed is True
        assert "BUY" in summary and "SELL" in summary

    def test_important_day_detected(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(is_important_day=True)
        prev = self._make_analysis()
        changed, summary = _change_summary(cur, prev)
        assert changed is True
        assert "Important day" in summary

    def test_conviction_change_ge_10_detected(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(conviction_score=80)
        prev = self._make_analysis(conviction_score=65)
        changed, summary = _change_summary(cur, prev)
        assert changed is True
        assert "Conviction" in summary

    def test_conviction_change_lt_10_not_detected(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(conviction_score=79)
        prev = self._make_analysis(conviction_score=72)
        changed, summary = _change_summary(cur, prev)
        assert changed is False

    def test_rsi_change_ge_5_detected(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(rsi=60.0)
        prev = self._make_analysis(rsi=54.0)
        changed, summary = _change_summary(cur, prev)
        assert changed is True
        assert "RSI" in summary

    def test_rsi_change_lt_5_not_detected(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(rsi=53.0)
        prev = self._make_analysis(rsi=50.0)
        changed, summary = _change_summary(cur, prev)
        assert changed is False

    def test_new_news_detected(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(news_summary="Breaking: earnings beat.")
        prev = self._make_analysis(news_summary="Old news.")
        changed, summary = _change_summary(cur, prev)
        assert changed is True
        assert "New news" in summary

    def test_same_news_not_detected(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(news_summary="Same news.")
        prev = self._make_analysis(news_summary="Same news.")
        changed, summary = _change_summary(cur, prev)
        assert changed is False

    def test_data_conflict_detected(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(data_conflicts="Price mismatch yf vs fh.")
        prev = self._make_analysis(data_conflicts=None)
        changed, summary = _change_summary(cur, prev)
        assert changed is True
        assert "conflict" in summary.lower()

    def test_signal_score_change_ge_2_detected(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(signal_convergence_score=8)
        prev = self._make_analysis(signal_convergence_score=5)
        changed, summary = _change_summary(cur, prev)
        assert changed is True
        assert "Signals" in summary

    def test_signal_score_change_lt_2_not_detected(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(signal_convergence_score=6)
        prev = self._make_analysis(signal_convergence_score=5)
        changed, summary = _change_summary(cur, prev)
        assert changed is False

    def test_no_changes_returns_false_empty_summary(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis()
        prev = self._make_analysis()
        changed, summary = _change_summary(cur, prev)
        assert changed is False
        assert summary == ""

    def test_summary_capped_at_4_parts(self):
        from routers.analysis import _change_summary
        cur = self._make_analysis(
            verdict="BUY",
            is_important_day=True,
            conviction_score=85,
            rsi=60.0,
            news_summary="New news.",
        )
        prev = self._make_analysis(
            verdict="SELL",
            conviction_score=70,
            rsi=50.0,
            news_summary="Old news.",
        )
        _, summary = _change_summary(cur, prev)
        parts = summary.split(" · ")
        assert len(parts) <= 4
