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

    def test_static_prompt_forbids_stale_knowledge_as_current(self, db_session):
        """Real production failure this guards against: the model told a user 'Pat
        Gelsinger was replaced by Lip-Bu Tan in 2024' as if it were fresh context,
        when a failed web_search should have just been disclosed as unavailable."""
        static, _ = build_system_prompt("nobody@example.com", db_session)
        low = static.lower()
        assert "don't have current data" in low
        assert "training" in low


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

    def test_shows_significant_correlation_to_a_watchlist_ticker(self, db_session):
        from datetime import date
        from models import TickerCorrelation
        _seed_analysis(db_session, "PBCORA")
        _seed_analysis(db_session, "PBCORB")
        db_session.add(WatchlistItem(user_email="corr@example.com", ticker="PBCORA"))
        db_session.add(WatchlistItem(user_email="corr@example.com", ticker="PBCORB"))
        db_session.add(TickerCorrelation(
            ticker_a="PBCORA", ticker_b="PBCORB", corr_90d=0.71, p_value_90d=0.001,
            significant=True, computed_date=date.today(),
        ))
        db_session.commit()
        from services.prompt_builder import build_ticker_dossier
        dossier = build_ticker_dossier("PBCORA", db_session, "corr@example.com")
        assert "Correlated in your portfolio" in dossier
        assert "PBCORB: +0.71" in dossier
        assert "moves with" in dossier

    def test_negative_correlation_labeled_as_hedge(self, db_session):
        from datetime import date
        from models import TickerCorrelation
        _seed_analysis(db_session, "PBHEDA")
        _seed_analysis(db_session, "PBHEDB")
        db_session.add(WatchlistItem(user_email="hedge@example.com", ticker="PBHEDA"))
        db_session.add(WatchlistItem(user_email="hedge@example.com", ticker="PBHEDB"))
        db_session.add(TickerCorrelation(
            ticker_a="PBHEDA", ticker_b="PBHEDB", corr_90d=-0.65, p_value_90d=0.002,
            significant=True, computed_date=date.today(),
        ))
        db_session.commit()
        from services.prompt_builder import build_ticker_dossier
        dossier = build_ticker_dossier("PBHEDA", db_session, "hedge@example.com")
        assert "PBHEDB: -0.65" in dossier
        assert "potential hedge" in dossier

    def test_insignificant_correlation_never_shown(self, db_session):
        from datetime import date
        from models import TickerCorrelation
        _seed_analysis(db_session, "PBNSGA")
        _seed_analysis(db_session, "PBNSGB")
        db_session.add(WatchlistItem(user_email="nosig@example.com", ticker="PBNSGA"))
        db_session.add(WatchlistItem(user_email="nosig@example.com", ticker="PBNSGB"))
        db_session.add(TickerCorrelation(
            ticker_a="PBNSGA", ticker_b="PBNSGB", corr_90d=0.3, p_value_90d=0.2,
            significant=False, computed_date=date.today(),
        ))
        db_session.commit()
        from services.prompt_builder import build_ticker_dossier
        dossier = build_ticker_dossier("PBNSGA", db_session, "nosig@example.com")
        assert "Correlated in your portfolio" not in dossier
        assert "PBNSGB" not in dossier

    def test_correlation_to_ticker_not_in_watchlist_not_shown(self, db_session):
        """A significant correlation to a ticker the user doesn't actually track isn't
        actionable — only surface pairs where both sides are in their own portfolio."""
        from datetime import date
        from models import TickerCorrelation
        _seed_analysis(db_session, "PBOWNA")
        db_session.add(WatchlistItem(user_email="onlyone@example.com", ticker="PBOWNA"))
        db_session.add(TickerCorrelation(
            ticker_a="PBOWNA", ticker_b="PBNOTOWNED", corr_90d=0.8, p_value_90d=0.001,
            significant=True, computed_date=date.today(),
        ))
        db_session.commit()
        from services.prompt_builder import build_ticker_dossier
        dossier = build_ticker_dossier("PBOWNA", db_session, "onlyone@example.com")
        assert "Correlated in your portfolio" not in dossier


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

    def test_other_ticker_shows_sector_and_ripple_snippet(self, db_session):
        """Sector/category + a short ripple snippet ride along in the compact line so
        the model can make cross-ticker connections (e.g. MU's ripple text naming
        NVIDIA) without a full get_stock_analysis call for every tracked ticker."""
        _seed_analysis(db_session, "PBFOCUS3", conviction_score=70)
        _seed_analysis(
            db_session, "PBSECTOR",
            sector="Technology",
            ripple_analysis="X's HBM dominance ripples directly into Y's pricing power for AI accelerators, a genuinely long snippet that exceeds one hundred twenty characters easily.",
        )
        db_session.add(WatchlistItem(user_email="u7@example.com", ticker="PBFOCUS3"))
        db_session.add(WatchlistItem(user_email="u7@example.com", ticker="PBSECTOR"))
        db_session.commit()
        _, dynamic = build_system_prompt("u7@example.com", db_session, conversation_ticker="PBFOCUS3")
        other_block = dynamic.split("OTHER TRACKED TICKERS")[1]
        assert "[Technology]" in other_block
        assert "Ripple: X's HBM dominance ripples directly into Y's pricing power" in other_block
        assert "…" in other_block  # truncated, not the full paragraph

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


class TestUserLearnings:
    """save_learning-sourced facts must appear in every future conversation for that
    user, regardless of ticker focus — that's the entire point of the feature."""

    def test_learning_appears_in_general_chat(self, db_session):
        from models import UserLearning
        db_session.add(UserLearning(user_email="learner1@example.com", learning="Manages 48 stocks total."))
        db_session.commit()
        _, dynamic = build_system_prompt("learner1@example.com", db_session)
        assert "THINGS TO REMEMBER ABOUT THIS USER" in dynamic
        assert "Manages 48 stocks total." in dynamic

    def test_learning_appears_regardless_of_ticker_focus(self, db_session):
        """The whole point: a learning saved in one (e.g. general) conversation must
        surface in a totally different, ticker-scoped conversation later."""
        from models import UserLearning
        _seed_analysis(db_session, "PBLEARN")
        db_session.add(WatchlistItem(user_email="learner2@example.com", ticker="PBLEARN"))
        db_session.add(UserLearning(user_email="learner2@example.com", learning="Prefers concise, systematic answers."))
        db_session.commit()
        _, dynamic = build_system_prompt("learner2@example.com", db_session, conversation_ticker="PBLEARN")
        assert "Prefers concise, systematic answers." in dynamic

    def test_no_learnings_section_when_none_saved(self, db_session):
        _, dynamic = build_system_prompt("nolearnings@example.com", db_session)
        assert "THINGS TO REMEMBER ABOUT THIS USER" not in dynamic

    def test_learnings_scoped_to_the_correct_user(self, db_session):
        from models import UserLearning
        db_session.add(UserLearning(user_email="userA@example.com", learning="Only userA's fact."))
        db_session.commit()
        _, dynamic = build_system_prompt("userB@example.com", db_session)
        assert "Only userA's fact." not in dynamic

    def test_learnings_capped_to_most_recent_15(self, db_session):
        from datetime import datetime, timedelta
        from models import UserLearning
        base = datetime(2026, 1, 1)
        for i in range(20):
            db_session.add(UserLearning(
                user_email="manylearn@example.com", learning=f"Fact number {i}.",
                created_at=base + timedelta(days=i),
            ))
        db_session.commit()
        _, dynamic = build_system_prompt("manylearn@example.com", db_session)
        # Only the 15 most recent (highest i) should appear
        assert "Fact number 19." in dynamic
        assert "Fact number 5." in dynamic
        assert "Fact number 4." not in dynamic
        assert "Fact number 0." not in dynamic
