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
        low = static.lower()
        assert "bull" in low and "bear" in low

    def test_static_prompt_keeps_plain_voice(self, db_session):
        static, _ = build_system_prompt("nobody@example.com", db_session)
        assert "jargon" in static.lower()


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

    def test_deep_dossier_shows_longterm_returns_and_ownership(self, db_session):
        _seed_analysis(
            db_session, "PBLT",
            stock_52w_change=-47.8, sp500_52w_change=20.1,
            stock_5y_change=-33.6, sp500_5y_change=72.3,
            inst_ownership_pct=0.85, short_float_pct=0.126, short_ratio=6.4,
            target_price_mean=67.5, target_price_high=88.0, target_price_low=42.0,
            analyst_count=25, analyst_consensus="BUY",
        )
        _, dynamic = build_system_prompt("u@example.com", db_session, conversation_ticker="PBLT")
        # Values already stored as percentages must not be scaled again
        assert "1yr -47.8%" in dynamic and "S&P +20.1%" in dynamic
        assert "5yr -33.6%" in dynamic and "S&P +72.3%" in dynamic
        # Ownership/short fields are fractions and should be pct-formatted
        assert "Inst 85.0%" in dynamic
        assert "Short float 12.6%" in dynamic
        # Analyst target range with count
        assert "BUY (25)" in dynamic and "$67.5 ($42.0–$88.0)" in dynamic

    def test_focus_ticker_is_case_insensitive(self, db_session):
        _seed_analysis(db_session, "PBCASE", conviction_score=50)
        _, dynamic = build_system_prompt("u@example.com", db_session, conversation_ticker="pbcase")
        assert "PBCASE — FULL ANALYSIS" in dynamic

    def test_no_focus_ticker_no_deep_block(self, db_session):
        db_session.add(WatchlistItem(user_email="nofocus@example.com", ticker="PBNONE"))
        db_session.commit()
        _, dynamic = build_system_prompt("nofocus@example.com", db_session)
        assert "FULL ANALYSIS" not in dynamic


class TestBuildTickerDossier:
    """build_ticker_dossier() is reused by both the initial focus ticker and the
    get_stock_analysis tool — one function, so quality can't drift between the two paths."""

    def test_returns_full_dossier_matching_focus_ticker_path(self, db_session):
        _seed_analysis(
            db_session, "PBTOOL",
            conviction_score=61, bull_case="Cheap on forward earnings.",
            bear_case="Margin compression risk.",
        )
        from services.prompt_builder import build_ticker_dossier
        dossier = build_ticker_dossier("pbtool", db_session, "u@example.com")
        assert "PBTOOL — FULL ANALYSIS" in dossier
        assert "61/100" in dossier
        assert "Cheap on forward earnings." in dossier
        assert "Margin compression risk." in dossier

    def test_unknown_ticker_returns_friendly_message_not_crash(self, db_session):
        from services.prompt_builder import build_ticker_dossier
        result = build_ticker_dossier("ZZNOPE", db_session, "u@example.com")
        assert "No analysis available" in result
        assert "ZZNOPE" in result

    def test_includes_position_for_a_ticker_the_user_holds(self, db_session):
        _seed_analysis(db_session, "PBPOS")
        db_session.add(WatchlistItem(user_email="holder@example.com", ticker="PBPOS", shares=10, avg_cost=40.0))
        db_session.commit()
        from services.prompt_builder import build_ticker_dossier
        dossier = build_ticker_dossier("PBPOS", db_session, "holder@example.com")
        assert "10 shares" in dossier
        assert "avg cost $40.00" in dossier


class TestCompactOtherTickers:
    """In a ticker-scoped conversation, every OTHER ticker should be a cheap numeric line —
    keeping everything needed for portfolio-wide screening, dropping only prose."""

    def test_other_ticker_gets_compact_line_not_full_paragraph(self, db_session):
        _seed_analysis(db_session, "PBFOCUS", conviction_score=70)
        _seed_analysis(
            db_session, "PBOTHER",
            conviction_score=55, rsi=28.0,
        )
        db_session.add(WatchlistItem(user_email="u2@example.com", ticker="PBFOCUS"))
        db_session.add(WatchlistItem(user_email="u2@example.com", ticker="PBOTHER"))
        db_session.commit()
        _, dynamic = build_system_prompt("u2@example.com", db_session, conversation_ticker="PBFOCUS")
        assert "PBOTHER: BUY" in dynamic
        assert "RSI 28.0" in dynamic
        assert "Solid setup." not in dynamic.split("OTHER TRACKED TICKERS")[1]

    def test_other_ticker_keeps_position_and_important_flag(self, db_session):
        _seed_analysis(db_session, "PBFOCUS2", conviction_score=70)
        _seed_analysis(
            db_session, "PBHELD", is_important_day=True,
            importance_reason="Verdict reversal.",
        )
        db_session.add(WatchlistItem(user_email="u3@example.com", ticker="PBFOCUS2"))
        db_session.add(WatchlistItem(user_email="u3@example.com", ticker="PBHELD", shares=5, avg_cost=100.0))
        db_session.commit()
        _, dynamic = build_system_prompt("u3@example.com", db_session, conversation_ticker="PBFOCUS2")
        assert "5 shares" in dynamic and "avg cost $100.00" in dynamic
        assert "⭐" in dynamic  # important-day flag survives the trim

    def test_focus_ticker_not_duplicated_in_compact_loop(self, db_session):
        _seed_analysis(db_session, "PBDUP", conviction_score=70)
        db_session.add(WatchlistItem(user_email="u4@example.com", ticker="PBDUP"))
        db_session.commit()
        _, dynamic = build_system_prompt("u4@example.com", db_session, conversation_ticker="PBDUP")
        # The compact-loop line format is "TICKER: verdict ..." — that specific pattern
        # must not appear a second time for the ticker already shown in full above.
        assert dynamic.count("PBDUP: BUY") == 0

    def test_general_chat_keeps_full_detail_unchanged(self, db_session):
        """No focus ticker => the trim doesn't apply; general chat is exactly the case
        meant to synthesize across the whole portfolio, so it keeps full paragraphs."""
        _seed_analysis(db_session, "PBGEN2")
        db_session.add(WatchlistItem(user_email="u5@example.com", ticker="PBGEN2"))
        db_session.commit()
        _, dynamic = build_system_prompt("u5@example.com", db_session)
        assert "Reasoning:    Solid setup." in dynamic  # full paragraph label, not the compact line

    def test_general_chat_context_is_byte_identical_across_calls(self, db_session):
        """Unordered .in_() queries have no guaranteed row order between calls, which
        silently breaks Anthropic's exact-prefix cache match on every turn — this is what
        production data showed: a fresh multi-thousand-token cache_write on nearly every
        message in a general (non-ticker) conversation instead of write-once/read-many."""
        for t in ["PBORD3", "PBORD1", "PBORD2"]:
            _seed_analysis(db_session, t)
            db_session.add(WatchlistItem(user_email="u6@example.com", ticker=t))
        db_session.commit()
        _, dynamic1 = build_system_prompt("u6@example.com", db_session)
        _, dynamic2 = build_system_prompt("u6@example.com", db_session)
        assert dynamic1 == dynamic2
