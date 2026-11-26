"""
google-genai was installed unpinned in the nightly; 3.0.0 (2026-11-06) moved to API v1, which
rejects thinking_config, and every Gemini verdict was null for three weeks while the AI
sentinel called it a "known gap". Covers the fix, the pins, and the deterministic alert.
"""
import json
import os
import re
import runpy
import sys
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import google
import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import nightly_health_check as health  # noqa: E402


def _day(rows, verdict_b=0.0, news=6.0):
    return {"rows": rows, "null_pct": {"verdict_b": verdict_b, "news": news}}


class TestEvaluate:
    def test_normal_night_passes(self):
        stats = {"null_rates_by_date": {"2026-11-05": _day(94, verdict_b=2.1, news=8.5)}}
        assert health.evaluate(stats, "2026-11-05") == []

    @pytest.mark.parametrize("day,word", [
        (_day(95, verdict_b=100.0), "Gemini"),          # the 2026-11-06 outage
        (_day(91, news=100.0), "News"),                 # the 2026-10-02 outage
        (_day(92, verdict_b=56.5), "Gemini"),           # the 2026-10-22 credit run-out
    ])
    def test_real_outages_fail(self, day, word):
        problems = health.evaluate({"null_rates_by_date": {"2026-11-06": day}}, "2026-11-06")
        assert len(problems) == 1 and word in problems[0]

    def test_limit_is_over_20_percent(self):
        at = {"null_rates_by_date": {"2026-11-06": _day(100, verdict_b=20.0)}}
        over = {"null_rates_by_date": {"2026-11-06": _day(100, verdict_b=21.0)}}
        assert health.evaluate(at, "2026-11-06") == []
        assert health.evaluate(over, "2026-11-06")

    def test_nothing_saved_fails_and_older_days_are_ignored(self):
        stats = {"null_rates_by_date": {"2026-11-05": _day(94, verdict_b=100.0)}}
        assert health.evaluate(stats, "2026-11-06") == ["No analyses saved since 2026-11-06."]

    def test_a_run_crossing_midnight_is_weighted_by_rows(self):
        stats = {"null_rates_by_date": {"2026-11-06": _day(90, verdict_b=0.0), "2026-11-07": _day(5, verdict_b=100.0)}}
        assert health.evaluate(stats, "2026-11-06") == []  # 5 of 95

    def test_a_source_the_backend_stops_reporting_fails(self):
        stats = {"null_rates_by_date": {"2026-11-06": {"rows": 94, "null_pct": {"verdict_b": 0.0}}}}
        assert health.evaluate(stats, "2026-11-06") == ["News headlines: not reported by the backend since 2026-11-06."]

    @pytest.mark.parametrize("verdict_b,code", [(0.0, 0), (100.0, 1)])
    def test_exit_code(self, verdict_b, code, monkeypatch, capsys):
        monkeypatch.setenv("BACKEND_URL", "http://x"); monkeypatch.setenv("ADMIN_SECRET", "s")
        stats = {"null_rates_by_date": {"2026-11-06": _day(94, verdict_b=verdict_b)}}
        with patch.object(health, "fetch_stats", return_value=stats):
            assert health.main(["--since", "2026-11-06"]) == code
        assert ("::error" in capsys.readouterr().out) == bool(code)


def test_reads_the_real_backend_response(client: TestClient, db_session):
    """Contract: the keys the check reads are the ones the endpoint actually returns."""
    from models import MarketDataCache, StockAnalysis
    os.environ["ADMIN_SECRET"] = "health-secret"
    today = date.today()
    for t in ("HCKA", "HCKB"):
        db_session.merge(MarketDataCache(ticker=t, cache_date=today, info_json="{}", news_json='[{"title": "x"}]'))
        db_session.add(StockAnalysis(ticker=t, analysis_date=today, verdict="WATCH", verdict_b=None))
    db_session.commit()
    stats = client.get("/jobs/admin/data-quality", params={"x_admin_secret": "health-secret", "days": 3}).json()
    assert {"verdict_b", "news"} <= set(stats["null_rates_by_date"][today.isoformat()]["null_pct"])
    assert not any("not reported" in p for p in health.evaluate(stats, today.isoformat()))


def test_gemini_call_uses_the_api_version_that_allows_thinking_config(monkeypatch):
    seen = {}
    answer = {"verdict": "WATCH", "reasoning": "r", "conviction_score": 40}

    class Client:
        def __init__(self, **kw):
            seen["client"] = kw
            self.models = SimpleNamespace(generate_content=self._generate)

        def _generate(self, **kw):
            seen["call"] = kw
            return SimpleNamespace(text=json.dumps(answer), usage_metadata=None)

    genai = ModuleType("google.genai")
    types = ModuleType("google.genai.types")
    types.HttpOptions = types.GenerateContentConfig = types.ThinkingConfig = lambda **kw: kw
    genai.Client, genai.types = Client, types
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", types)
    monkeypatch.setattr(google, "genai", genai, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(sys, "argv", ["nightly_verdict_b.py", "ZZGEM"])
    summary, out = Path("/tmp/summary_ZZGEM.json"), Path("/tmp/verdict_b_ZZGEM.json")
    summary.write_text(json.dumps({"price": 10.0, "news": []}))
    try:
        runpy.run_path(str(REPO / "scripts" / "nightly_verdict_b.py"), run_name="__main__")
        assert json.loads(out.read_text()) == answer
    finally:
        summary.unlink(missing_ok=True); out.unlink(missing_ok=True)
    assert seen["client"]["http_options"] == {"api_version": "v1beta"}
    assert seen["call"]["config"]["thinking_config"] == {"thinking_budget": 0}
    assert seen["call"]["config"]["response_mime_type"] == "application/json"


class TestNightlyWiring:
    workflow = (REPO / ".github" / "workflows" / "nightly.yml").read_text()
    pins = [l for l in (REPO / "scripts" / "requirements-nightly.txt").read_text().splitlines() if l and not l.startswith("#")]

    def test_every_nightly_package_is_pinned(self):
        assert len(self.pins) > 10 and all(re.fullmatch(r"[A-Za-z0-9_.\-]+==[A-Za-z0-9_.\-]+", p) for p in self.pins)
        assert any(p.startswith("google-genai==") for p in self.pins) and any(p.startswith("yfinance==") for p in self.pins)

    def test_workflow_installs_only_from_the_pinned_file(self):
        installs = re.findall(r"pip install[^\n#]*", self.workflow)
        assert [i.strip() for i in installs] == ["pip install -r scripts/requirements-nightly.txt"]

    def test_health_check_runs_after_analysis_even_if_batches_failed(self):
        job = self.workflow[self.workflow.index("  health-check:"):]
        assert "needs: [split, analyze]" in job
        assert "!cancelled() && needs.split.outputs.has_work == 'true'" in job
        assert 'nightly_health_check.py --since "${{ needs.split.outputs.run_date }}"' in job
        assert "run_date=" in self.workflow
