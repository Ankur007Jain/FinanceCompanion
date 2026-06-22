"""
Tests for the chatbot system-prompt builder — committee lens + deep ticker block.
"""
from datetime import date

from models import StockAnalysis, WatchlistItem
from services.prompt_builder import build_system_prompt


def _seed_analysis(db, ticker: str, **extra):
    a = StockAnalysis(
        ticker=ticker, analysis_date=date.today(),
        current_price=100.0, day_change_pct=1.0,
        week_52_high=120.0, week_52_low=80.0, range_position_pct=50.0,
        ma_50=98.0, ma_200=95.0, verdict="BUY", reasoning="Solid setup.",
        **extra,
    )
    db.add(a)
    db.commit()
    return a


class TestCommitteeLens:
    def test_static_prompt_mentions_bull_and_bear(self, db_session):
        static, _ = build_system_prompt("nobody@example.com", db_session)
        assert "BULL" in static and "BEAR" in static

    def test_static_prompt_keeps_plain_voice(self, db_session):
        static, _ = build_system_prompt("nobody@example.com", db_session)
        assert "no jargon" in static.lower()


class TestDeepBlock:
    def test_focus_ticker_injects_deep_dossier(self, db_session):
        _seed_analysis(
            db_session, "PBDEEP",
            conviction_score=82, risk_level="MED", confidence="High",
            bull_case="Cash flow funds buybacks.",
            bear_case="Pricey multiple, no margin for error.",
            thesis_invalidation="A guidance cut next quarter.",
        )
        _, dynamic = build_system_prompt("u@example.com", db_session, conversation_ticker="PBDEEP")
        assert "PBDEEP — FULL ANALYSIS" in dynamic
        assert "82/100" in dynamic
        assert "Cash flow funds buybacks." in dynamic
        assert "Pricey multiple" in dynamic
        assert "A guidance cut next quarter." in dynamic

    def test_focus_ticker_is_case_insensitive(self, db_session):
        _seed_analysis(db_session, "PBCASE", conviction_score=50)
        _, dynamic = build_system_prompt("u@example.com", db_session, conversation_ticker="pbcase")
        assert "PBCASE — FULL ANALYSIS" in dynamic

    def test_no_focus_ticker_no_deep_block(self, db_session):
        db_session.add(WatchlistItem(user_email="nofocus@example.com", ticker="PBNONE"))
        db_session.commit()
        _, dynamic = build_system_prompt("nofocus@example.com", db_session)
        assert "FULL ANALYSIS" not in dynamic
