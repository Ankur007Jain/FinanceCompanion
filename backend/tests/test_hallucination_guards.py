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
        content = (REPO_ROOT / ".github" / "workflows" / "nightly.yml").read_text()
        assert "conviction_score" in content
        assert "30" in content
        idx = content.find("Even when verdict_agreement=true")
        assert idx != -1


class TestDataConflictsSurfacedToAskAI:
    def test_data_conflicts_rendered_in_deep_formatter(self):
        content = (REPO_ROOT / "backend" / "services" / "prompt_builder.py").read_text()
        assert "data_conflicts" in content
        assert "Data caution" in content
