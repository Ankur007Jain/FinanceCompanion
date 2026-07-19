"""
Tests for the stock-memory feedback loop:
- GET /jobs/admin/memories (nightly agents fetch past lessons)
- NO_UPDATE handling in both memory-update paths (startswith, not exact match —
  the model sometimes writes NO_UPDATE and keeps going, which used to leak the
  refusal text into stored memory)
- Narrative-arc report prompt structure
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from models import StockMemory
from services.stock_memory import append_lesson, maybe_update_stock_memory, update_memory_from_report

ADMIN_SECRET = "test-admin-secret"


def _seed_memory(db, ticker, narrative):
    db.merge(StockMemory(ticker=ticker, memory_narrative=narrative))
    db.commit()


class TestMemoriesEndpoint:
    def test_rejects_bad_secret(self, client: TestClient):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        r = client.get("/jobs/admin/memories", params={"x_admin_secret": "wrong"})
        assert r.status_code == 401

    def test_returns_memories(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        _seed_memory(db_session, "MEMA", "Past mistakes to avoid: stale analyst targets.")
        r = client.get("/jobs/admin/memories", params={"x_admin_secret": ADMIN_SECRET})
        assert r.status_code == 200
        assert r.json()["memories"]["MEMA"].startswith("Past mistakes")

    def test_ticker_filter(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        _seed_memory(db_session, "MEMB", "Lesson B.")
        _seed_memory(db_session, "MEMC", "Lesson C.")
        r = client.get(
            "/jobs/admin/memories",
            params={"x_admin_secret": ADMIN_SECRET, "tickers": "memb, ZZNONE"},
        )
        memories = r.json()["memories"]
        assert "MEMB" in memories
        assert "MEMC" not in memories
        assert "ZZNONE" not in memories

    def test_skips_empty_narratives(self, client: TestClient, db_session):
        os.environ["ADMIN_SECRET"] = ADMIN_SECRET
        _seed_memory(db_session, "MEMD", "")
        r = client.get(
            "/jobs/admin/memories",
            params={"x_admin_secret": ADMIN_SECRET, "tickers": "MEMD"},
        )
        assert "MEMD" not in r.json()["memories"]


def _mock_anthropic(response_text: str):
    """AsyncAnthropic mock whose messages.create returns the given text."""
    resp = MagicMock()
    resp.content = [MagicMock(text=response_text)]
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=resp)
    return client


class TestNoUpdateHandling:
    @pytest.mark.asyncio
    async def test_nightly_path_skips_no_update_with_trailing_text(self, db_session):
        _seed_memory(db_session, "NOUP1", "Original memory.")
        mock = _mock_anthropic("NO_UPDATE\n\nThe existing memory already covers this.")
        with patch("services.stock_memory.anthropic.AsyncAnthropic", return_value=mock):
            await maybe_update_stock_memory("NOUP1", "WATCH", "r", "n", "", db_session)
        db_session.expire_all()
        assert db_session.get(StockMemory, "NOUP1").memory_narrative == "Original memory."

    @pytest.mark.asyncio
    async def test_report_path_skips_no_update_with_trailing_text(self, db_session):
        _seed_memory(db_session, "NOUP2", "Original memory.")
        mock = _mock_anthropic("NO_UPDATE — the report shows no clear mistakes.")
        with patch("services.stock_memory.anthropic.AsyncAnthropic", return_value=mock):
            await update_memory_from_report("NOUP2", "## Report", db_session)
        db_session.expire_all()
        assert db_session.get(StockMemory, "NOUP2").memory_narrative == "Original memory."

    @pytest.mark.asyncio
    async def test_real_update_still_saves(self, db_session):
        _seed_memory(db_session, "NOUP3", "Original memory.")
        mock = _mock_anthropic("Updated narrative. Past mistakes to avoid: chasing stale targets.")
        with patch("services.stock_memory.anthropic.AsyncAnthropic", return_value=mock):
            await update_memory_from_report("NOUP3", "## Report", db_session)
        db_session.expire_all()
        assert "Past mistakes" in db_session.get(StockMemory, "NOUP3").memory_narrative


class TestAppendLesson:
    """append_lesson() is the shared write path for both the weekly Scorecard's
    lesson-append endpoint and chat's flag_stock_correction tool — same tests should
    hold for either caller since it's the identical function underneath."""

    def test_creates_memory_when_missing(self, db_session):
        mem = append_lesson("ALSA", "Revenue guidance cut in Q2.", "Chat", db_session)
        assert mem.memory_narrative == "[Chat] Revenue guidance cut in Q2."
        assert mem.update_count == 1

    def test_appends_to_existing_memory_with_source_tag(self, db_session):
        _seed_memory(db_session, "ALSB", "Existing context.")  # update_count left unset (None)
        mem = append_lesson("ALSB", "CEO stepped down.", "Chat", db_session)
        assert mem.memory_narrative.startswith("Existing context.")
        assert "[Chat] CEO stepped down." in mem.memory_narrative
        assert mem.update_count == 1

    def test_scorecard_and_chat_use_distinct_tags(self, db_session):
        append_lesson("ALSC", "From scorecard.", "Scorecard", db_session)
        mem = append_lesson("ALSC", "From chat.", "Chat", db_session)
        assert "[Scorecard] From scorecard." in mem.memory_narrative
        assert "[Chat] From chat." in mem.memory_narrative

    def test_caps_total_length(self, db_session):
        db_session.merge(StockMemory(ticker="ALSD", memory_narrative="x" * 1150))
        db_session.commit()
        mem = append_lesson("ALSD", "y" * 500, "Chat", db_session)
        assert len(mem.memory_narrative) <= 1200

    def test_newest_lesson_always_survives_when_over_budget(self, db_session):
        """The actual bug, reproduced: real production data showed a Scorecard lesson
        for MU never landed (memory was exactly at the 1200-char cap, no [Scorecard]
        tag anywhere), while TMUS's did — purely because TMUS's existing memory was
        shorter. The old code did (existing + new)[:1200], keeping stale front content
        and silently dropping the new lesson at the end whenever memory was already
        full. Reproducing that exact scenario here."""
        db_session.merge(StockMemory(ticker="ALSF", memory_narrative="x" * 1150))
        db_session.commit()
        mem = append_lesson("ALSF", "5 failed BUYs — avoid entries into this downtrend.", "Scorecard", db_session)
        assert "[Scorecard] 5 failed BUYs" in mem.memory_narrative
        assert len(mem.memory_narrative) <= 1200

    def test_oldest_paragraph_dropped_first_not_hard_truncated(self, db_session):
        """Prefers dropping a whole stale paragraph over an arbitrary mid-word cut."""
        db_session.merge(StockMemory(
            ticker="ALSG",
            memory_narrative="[Chat] Oldest lesson, should be dropped first.\n\n" + ("z" * 1180),
        ))
        db_session.commit()
        mem = append_lesson("ALSG", "Newest lesson must survive.", "Scorecard", db_session)
        assert "Newest lesson must survive." in mem.memory_narrative
        assert "Oldest lesson, should be dropped first." not in mem.memory_narrative
        assert len(mem.memory_narrative) <= 1200

    def test_ticker_uppercased(self, db_session):
        mem = append_lesson("alse", "lowercase input.", "Chat", db_session)
        assert mem.ticker == "ALSE"


class TestNarrativeReportPrompt:
    def test_prompt_is_a_chronological_story_not_parallel_sections(self):
        from routers.analysis import _REPORT_PROMPT
        # New narrative arc sections
        assert "The Setup" in _REPORT_PROMPT
        assert "Where This Leaves Us" in _REPORT_PROMPT
        assert "What Proves It / What Breaks It" in _REPORT_PROMPT
        # Old parallel-section headers must be gone
        assert "Verdict Trajectory" not in _REPORT_PROMPT
        assert "Conviction Trend" not in _REPORT_PROMPT

    def test_prompt_keeps_honest_self_assessment(self):
        # update_memory_from_report() extracts lessons from "what the AI got wrong"
        # content — the narrative rewrite must still ask for it.
        from routers.analysis import _REPORT_PROMPT
        assert "wrong" in _REPORT_PROMPT.lower()
