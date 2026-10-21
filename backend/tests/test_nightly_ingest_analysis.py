"""
scripts/nightly_ingest_analysis.py replaces the agent-built Step 4 POST, which dropped
`rsi` (#132) and later `reasoning` (5 tickers on each of 2026-10-12, 10-19, 10-20) because
each batch improvised its own payload code from an incomplete field list in the prompt.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import nightly_ingest_analysis as nia  # noqa: E402

SUMMARY = {
    "ticker": "NIAX", "price": 120.5, "change_pct": -1.25, "hi52": 150.0, "lo52": 90.0, "range_pct": 50.8,
    "ma50": 118.0, "ma200": 110.0, "rsi": 44.9, "analyst": "BUY", "analyst_count": 20, "upside_pct": 12.0,
    "target_mean": 135.0, "target_high": 160.0, "target_low": 100.0, "support_20d": 115.0, "resistance_20d": 125.0,
    "pivot": 120.0, "piv_r1": 122.0, "piv_s1": 118.0, "sector": "Technology", "industry": "Software",
    "sp500_day_chg": -0.4, "sector_etf": "XLK", "sector_day_chg": -0.8, "relative_strength_1d": -0.45,
    "sp500_52w_change": 15.0, "stock_52w_change": 20.0, "sp500_5y_change": 70.0, "stock_5y_change": 90.0,
    "fh_price": 120.4, "fh_analyst": "BUY", "pe_trailing": 30.0, "pe_forward": 25.0, "revenue_growth": 0.15,
    "earnings_growth": 0.2, "profit_margin": 0.25, "debt_to_equity": 40.0, "free_cashflow": 1e9,
    "return_on_equity": 0.3, "beta": 1.1, "short_float_pct": 0.02, "short_ratio": 1.5,
    "inst_ownership_pct": 0.7, "insider_ownership_pct": 0.05, "dividend_yield": 0.5, "market_cap": 5e10,
    "data_conflicts": "fh_price differs by 0.1%", "earnings_date": "2026-11-03",
}
CONV = {"signal_convergence_score": 7, "convergence_details": {"rsi_ok": True, "sector_outperforming": False}}
VA = {
    "verdict": "BUY", "entry_target": 119.0, "exit_target": 135.0, "stop_loss": 112.0, "hold_period": "2-4 weeks",
    "reasoning": "Full multi-line reasoning.", "conviction_score": 72, "risk_level": "MED", "confidence": "Medium",
    "bull_case": "Bull.", "bear_case": "Bear.", "thesis_invalidation": "Breaks 112.", "news_summary": "News.",
    "ripple_analysis": "Ripple.", "is_important_day": True, "importance_reason": "Breakout.",
    "entry_quality": "FAIR", "hold_and_forget_rating": "CHECK_MONTHLY", "position_size_pct": "5-8%",
    "scenario_bull": "Up.", "scenario_bull_pct": 15.0, "scenario_bull_prob": 30,
    "scenario_base": "Flat.", "scenario_base_pct": 3.0, "scenario_base_prob": 50,
    "scenario_bear": "Down.", "scenario_bear_pct": -10.0, "scenario_bear_prob": 20, "dont_panic_note": "",
}
VB = {"verdict": "BUY", "conviction_score": 65, "gemini_tokens_input": 1800, "gemini_tokens_output": 400}


class TestJudge:
    @pytest.mark.parametrize("a,b,final", [
        ("BUY", "HOLD", "WATCH"), ("HOLD", "BUY", "WATCH"), ("BUY", "SELL", "WATCH"), ("SELL", "BUY", "WATCH"),
        ("BUY", "WATCH", "WATCH"), ("WATCH", "BUY", "WATCH"), ("HOLD", "SELL", "WATCH"), ("SELL", "HOLD", "WATCH"),
        ("HOLD", "WATCH", "WATCH"), ("WATCH", "HOLD", "WATCH"), ("SELL", "WATCH", "SELL"), ("WATCH", "SELL", "SELL"),
    ])
    def test_every_disagreement_is_covered_both_ways(self, a, b, final):
        assert nia.judge({"verdict": a, "conviction_score": 60}, {"verdict": b, "conviction_score": 60}, None)[:2] == (final, False)

    def test_agreement_and_gemini_unavailable(self):
        assert nia.judge({"verdict": "BUY", "conviction_score": 70}, {"verdict": "BUY", "conviction_score": 65}, None) == ("BUY", True, None)
        assert nia.judge({"verdict": "HOLD"}, {"verdict": None}, "ignored") == ("HOLD", None, None)
        assert nia.judge({"verdict": "HOLD"}, None, None) == ("HOLD", None, None)

    def test_split_reason_uses_agent_sentence_else_a_factual_fallback(self):
        a, b = {"verdict": "BUY", "conviction_score": 70}, {"verdict": "SELL", "conviction_score": 40}
        assert nia.judge(a, b, " Claude likes RSI; Gemini fears earnings. \n")[2] == "Claude likes RSI; Gemini fears earnings."
        assert nia.judge(a, b, None)[2] == "Claude says BUY, Gemini says SELL."

    def test_confidence_gap_on_agreement_is_surfaced(self):
        _, agreement, reason = nia.judge({"verdict": "BUY", "conviction_score": 75}, {"verdict": "BUY", "conviction_score": 40}, None)
        assert agreement is True and "Claude 75/100 vs Gemini 40/100" in reason


class TestBuildPayload:
    def test_carries_the_fields_that_went_missing(self):
        p = nia.build_payload("NIAX", "2026-10-21", SUMMARY, CONV, VA, VB)
        assert p["reasoning"] == "Full multi-line reasoning."  # 2026-10-12/19/20
        assert p["rsi"] == 44.9  # issue #132
        assert (p["entry_target"], p["exit_target"], p["news_summary"], p["ripple_analysis"], p["is_important_day"]) == \
               (119.0, 135.0, "News.", "Ripple.", True)
        assert p["price_change_pct"] == -1.25 and p["current_price"] == 120.5
        assert p["conviction_score_raw"] == 72 and p["signal_convergence_score"] == 7
        assert json.loads(p["convergence_details"]) == CONV["convergence_details"]
        assert (p["gemini_tokens_input"], p["gemini_tokens_output"]) == (1800, 400)
        assert (p["verdict"], p["verdict_a"], p["verdict_b"], p["verdict_agreement"]) == ("BUY", "BUY", "BUY", True)

    def test_matches_the_backend_contract_exactly(self):
        """Every field the backend accepts is produced, and nothing it doesn't know about —
        so a field added to the schema (or the summary) can't silently be left out again."""
        from schemas import IngestAnalysisRequest
        p = nia.build_payload("NIAX", "2026-10-21", SUMMARY, CONV, VA, VB)
        assert set(p) == set(IngestAnalysisRequest.model_fields)

    def test_optional_fields_omitted_when_absent(self):
        summary = {**SUMMARY, "data_conflicts": None, "earnings_date": None}
        p = nia.build_payload("NIAX", "2026-10-21", summary, CONV, VA, {"verdict": None})
        assert "data_conflicts" not in p and "earnings_date" not in p and "gemini_tokens_input" not in p
        assert p["verdict_b"] is None and p["verdict_agreement"] is None

    @pytest.mark.parametrize("field", ["reasoning", "verdict", "conviction_score", "bull_case"])
    def test_refuses_to_save_without_required_fields(self, field):
        with pytest.raises(nia.InputError, match=field):
            nia.build_payload("NIAX", "2026-10-21", SUMMARY, CONV, {**VA, field: None}, VB)

    def test_refuses_an_invalid_verdict(self):
        with pytest.raises(nia.InputError, match="invalid verdict"):
            nia.build_payload("NIAX", "2026-10-21", SUMMARY, CONV, {**VA, "verdict": "STRONG BUY"}, VB)


class TestMain:
    def _write(self, tmp_path, **override):
        files = {"summary": SUMMARY, "convergence": CONV, "verdict_a": VA, "verdict_b": VB, **override}
        for name, data in files.items():
            if data is not None:
                (tmp_path / f"{name}_NIAX.json").write_text(json.dumps(data))

    def test_missing_reasoning_exits_2_and_never_posts(self, tmp_path, capsys):
        self._write(tmp_path, verdict_a={**VA, "reasoning": ""})
        with patch.object(nia, "post") as post:
            assert nia.main(["NIAX"], tmp=str(tmp_path)) == 2
        post.assert_not_called()
        assert "NOT SAVED" in capsys.readouterr().out

    def test_missing_input_file_exits_2(self, tmp_path):
        self._write(tmp_path, convergence=None)
        assert nia.main(["NIAX"], tmp=str(tmp_path)) == 2

    def test_split_reason_file_is_picked_up(self, tmp_path, monkeypatch):
        self._write(tmp_path, verdict_b={"verdict": "WATCH", "conviction_score": 50})
        (tmp_path / "split_reason_NIAX.txt").write_text("Gemini flags earnings risk.")
        monkeypatch.setenv("BACKEND_URL", "http://x"); monkeypatch.setenv("JOB_SECRET", "s")
        with patch.object(nia, "post", return_value=(200, "{}")) as post:
            assert nia.main(["NIAX"], tmp=str(tmp_path)) == 0
        sent = post.call_args.args[0]
        assert (sent["verdict"], sent["verdict_agreement"], sent["split_reason"]) == ("WATCH", False, "Gemini flags earnings risk.")

    def test_http_error_exits_1(self, tmp_path, monkeypatch):
        self._write(tmp_path)
        monkeypatch.setenv("BACKEND_URL", "http://x"); monkeypatch.setenv("JOB_SECRET", "s")
        with patch.object(nia, "post", return_value=(422, "bad")):
            assert nia.main(["NIAX"], tmp=str(tmp_path)) == 1


def test_backend_accepts_the_payload_and_stores_reasoning(client: TestClient):
    """End to end against the real ingest endpoint: the exact payload this script builds is
    accepted and every previously-dropped field comes back out."""
    p = nia.build_payload("NIAX", "2026-10-21", SUMMARY, CONV, VA, VB)
    r = client.post("/jobs/ingest-analysis", params={"x_job_secret": "test-job-secret"}, json=p)
    assert r.status_code == 200, r.text
    with patch("routers.auth.id_token.verify_oauth2_token", return_value={"email": "nia@example.com", "name": "N"}):
        a = client.get("/analysis/NIAX/latest", params={"id_token": "x"}).json()
    assert a["reasoning"] == "Full multi-line reasoning."
    assert a["rsi"] == 44.9 and a["entry_target"] == 119.0 and a["news_summary"] == "News."
    assert a["verdict"] == "BUY" and a["is_important_day"] is True
