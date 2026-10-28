"""Static checks that grounding ('never invent a number') language is present on every
LLM-generation surface, and that data_conflicts (incl. target-sanity warnings) reaches Ask AI."""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_GROUNDING_RE = re.compile(r"never invent", re.IGNORECASE)


class TestGroundingLanguagePresent:
    def test_ask_ai_static_system_prompt(self):
        content = (REPO_ROOT / "backend" / "services" / "prompt_builder.py").read_text()
        assert _GROUNDING_RE.search(content)

    def test_nightly_verdict_a_workflow(self):
        content = (REPO_ROOT / ".github" / "workflows" / "nightly.yml").read_text()
        assert _GROUNDING_RE.search(content)

    def test_nightly_verdict_b_script(self):
        content = (REPO_ROOT / "scripts" / "nightly_verdict_b.py").read_text()
        assert _GROUNDING_RE.search(content)

    def test_ai_report_system_prompt(self):
        content = (REPO_ROOT / "backend" / "routers" / "analysis.py").read_text()
        assert _GROUNDING_RE.search(content)

    def test_stock_memory_prompts(self):
        content = (REPO_ROOT / "backend" / "services" / "stock_memory.py").read_text()
        assert len(_GROUNDING_RE.findall(content)) >= 2


class TestJudgeConvictionDivergence:
    def test_judge_step_flags_conviction_gap_even_on_agreement(self):
        # The agreement table + gap check moved into scripts/nightly_ingest_analysis.py (see
        # test_nightly_ingest_analysis.py::TestJudge); the prompt still asks the agent for the
        # explanatory sentence when the models agree but confidence differs by 30+.
        content = (REPO_ROOT / ".github" / "workflows" / "nightly.yml").read_text()
        assert "agree but" in content and "30+ points" in content
        script = (REPO_ROOT / "scripts" / "nightly_ingest_analysis.py").read_text()
        assert "_CONVICTION_GAP = 30" in script


class TestDataConflictsSurfacedToAskAI:
    def test_data_conflicts_rendered_in_deep_formatter(self):
        content = (REPO_ROOT / "backend" / "services" / "prompt_builder.py").read_text()
        assert "data_conflicts" in content
        assert "Data caution" in content


class TestHardFinancialFigureGrounding:
    """Regression for the MSFT $331B fabricated-revenue incident: the chat system prompt
    must explicitly warn that absolute dollar figures (revenue/earnings/market cap) are
    not in the dossier and require a web_search citation, and must include an
    order-of-magnitude sanity-check instruction."""

    def test_absolute_dollar_figures_require_websearch_citation(self):
        content = (REPO_ROOT / "backend" / "services" / "prompt_builder.py").read_text()
        # Must call out that absolute revenue/earnings are not in the dossier.
        assert "revenue" in content.lower()
        assert "web_search" in content
        # Must instruct the model to sanity-check magnitudes rather than parroting a
        # confidently-wrong figure.
        assert "sanity-check" in content.lower() or "order of magnitude" in content.lower()


class TestWebSearchNumberRules:
    """Issue #165 (STX, 2026-10-28): the chat relayed MarketBeat's "58.61% upside" — computed
    against the article's ~$630 snapshot — right after quoting $667.85 itself; dropped
    Citigroup, which the user asked about, for an unrequested firm; and called MarketBeat's
    average target "down from" the dossier's Yahoo mean."""

    def _system(self):
        import sys
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        from services.prompt_builder import _STATIC_SYSTEM
        return _STATIC_SYSTEM

    def test_price_derived_percentages_are_recomputed(self):
        s = self._system()
        assert "Never relay it as-is: recompute it" in s
        assert "must reconcile with the price you've stated" in s

    def test_named_items_are_each_answered_never_swapped(self):
        s = self._system()
        assert "answer each one they named" in s and "never drop it silently" in s
        assert "never fill its slot with a firm or ticker they didn't ask about" in s

    def test_cross_source_figures_are_not_a_trend(self):
        s = self._system()
        assert "Figures from different sources are not a time series" in s
        assert 'never call one "down from" or "up from" the other' in s
