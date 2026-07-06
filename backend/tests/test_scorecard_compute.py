"""
Tests for the Verdict Scorecard's outcome math (scripts/scorecard_compute.py).
Synthetic prices, no network — verifies the replay logic the weekly agent trusts.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from scorecard_compute import compute_report, conviction_band  # noqa: E402

TODAY = date(2026, 7, 6)


def _daily_closes(start: date, prices: list[float]) -> dict[str, float]:
    return {(start + timedelta(days=i + 1)).isoformat(): p for i, p in enumerate(prices)}


def _analysis(ticker, d, verdict="BUY", price=100.0, conviction=70, exit_target=110.0, stop_loss=90.0):
    return {
        "ticker": ticker, "date": d.isoformat(), "verdict": verdict, "conviction": conviction,
        "price": price, "entry_target": 99.0, "exit_target": exit_target, "stop_loss": stop_loss,
        "hold_period": "2-4 weeks",
    }


class TestComputeReport:
    def test_forward_returns_and_win_rate(self):
        d = TODAY - timedelta(days=20)
        # price 100 -> day5 close 105 => +5% 5d return
        closes = {"WINR": _daily_closes(d, [101, 102, 103, 104, 105, 106, 107, 108])}
        report = compute_report([_analysis("WINR", d)], closes, today=TODAY)
        assert report["verdicts_evaluated"] == 1
        buy = report["by_verdict"]["BUY"]
        assert buy["avg_ret_5d_pct"] == 5.0
        assert buy["win_rate_5d_pct"] == 100.0

    def test_target_hit_before_stop(self):
        d = TODAY - timedelta(days=20)
        closes = {"TGTH": _daily_closes(d, [102, 106, 111, 108, 107])}  # crosses 110 on day 3
        report = compute_report([_analysis("TGTH", d)], closes, today=TODAY)
        assert report["buy_target_vs_stop"] == {"target_hit": 1}

    def test_stopped_out_becomes_notable_failure(self):
        d = TODAY - timedelta(days=20)
        closes = {"STOP": _daily_closes(d, [96, 93, 89, 88, 87])}  # crosses 90 stop on day 3
        report = compute_report([_analysis("STOP", d, conviction=80)], closes, today=TODAY)
        assert report["buy_target_vs_stop"] == {"stopped_out": 1}
        assert report["notable_failures"][0]["ticker"] == "STOP"
        assert report["notable_failures"][0]["resolution"] == "stopped_out"

    def test_conviction_bands_group_buys(self):
        d = TODAY - timedelta(days=20)
        closes = {
            "BNDA": _daily_closes(d, [101, 102, 103, 104, 105]),
            "BNDB": _daily_closes(d, [99, 98, 97, 96, 95]),
        }
        analyses = [
            _analysis("BNDA", d, conviction=75),
            _analysis("BNDB", d, conviction=40),
        ]
        report = compute_report(analyses, closes, today=TODAY)
        assert report["buy_by_conviction_band"]["70+"]["avg_ret_5d_pct"] == 5.0
        assert report["buy_by_conviction_band"]["<50"]["avg_ret_5d_pct"] == -5.0

    def test_recent_analyses_excluded(self):
        d = TODAY - timedelta(days=3)  # inside the 7-day exclusion window
        closes = {"RCNT": _daily_closes(d, [101, 102, 103, 104, 105])}
        report = compute_report([_analysis("RCNT", d)], closes, today=TODAY)
        assert report["verdicts_evaluated"] == 0

    def test_missing_price_data_skipped_not_crashed(self):
        d = TODAY - timedelta(days=20)
        report = compute_report([_analysis("NOPX", d)], {}, today=TODAY)
        assert report["verdicts_evaluated"] == 0

    def test_non_buy_verdicts_tracked_but_not_resolved(self):
        d = TODAY - timedelta(days=20)
        closes = {"WTCH": _daily_closes(d, [101, 102, 103, 104, 105])}
        report = compute_report([_analysis("WTCH", d, verdict="WATCH")], closes, today=TODAY)
        assert report["by_verdict"]["WATCH"]["n"] == 1
        assert report["buy_target_vs_stop"] == {}


class TestConvictionBand:
    def test_bands(self):
        assert conviction_band(85) == "70+"
        assert conviction_band(70) == "70+"
        assert conviction_band(55) == "50-69"
        assert conviction_band(30) == "<50"
        assert conviction_band(None) == "unknown"
