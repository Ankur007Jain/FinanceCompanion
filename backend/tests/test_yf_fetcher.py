"""
Unit tests for yf_fetcher._extract_cashflow.

Regression coverage for a real data-quality bug: info["freeCashflow"] was confirmed
stale/wrong against MSFT (info said $16.4B, the actual cash flow statement said $67.0B).
Free cash flow must come from the real cash flow statement, not the info dict.
"""
import pandas as pd

from agents.yf_fetcher import _extract_cashflow


def _cf(rows: dict, col="2026-06-30") -> pd.DataFrame:
    """Builds a DataFrame shaped like yfinance's cashflow statement: line items as the
    index, one column per period. Most recent period is always column 0 in the real API."""
    return pd.DataFrame({col: pd.Series(rows)})


class TestExtractCashflow:
    def test_none_returns_none(self):
        assert _extract_cashflow(None) is None

    def test_empty_dataframe_returns_none(self):
        assert _extract_cashflow(pd.DataFrame()) is None

    def test_uses_free_cash_flow_row_when_present(self):
        cf = _cf({"Free Cash Flow": 66_987_000_000.0, "Operating Cash Flow": 182_935_000_000.0,
                  "Capital Expenditure": -115_948_000_000.0})
        result = _extract_cashflow(cf)
        assert result["free_cash_flow"] == 66_987_000_000.0
        assert result["operating_cash_flow"] == 182_935_000_000.0
        assert result["capital_expenditure"] == -115_948_000_000.0

    def test_computes_from_operating_cf_and_capex_when_fcf_row_missing(self):
        cf = _cf({"Operating Cash Flow": 100.0, "Capital Expenditure": -40.0})
        result = _extract_cashflow(cf)
        assert result["free_cash_flow"] == 60.0

    def test_nan_free_cash_flow_falls_back_to_computed(self):
        cf = _cf({"Free Cash Flow": float("nan"), "Operating Cash Flow": 100.0, "Capital Expenditure": -40.0})
        result = _extract_cashflow(cf)
        assert result["free_cash_flow"] == 60.0

    def test_missing_all_relevant_rows_returns_none(self):
        cf = _cf({"Some Other Line Item": 123.0})
        assert _extract_cashflow(cf) is None
