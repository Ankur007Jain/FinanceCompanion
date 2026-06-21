"""
Analyst Agent — fetches analyst consensus, price targets, and fundamentals
from yfinance (primary) and Finnhub (secondary), then cross-validates.
"""
import json
import os
import asyncio
from dataclasses import dataclass, field
from typing import Optional

import finnhub
import yfinance as yf


@dataclass
class AnalystData:
    consensus: str          # "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL" | "N/A"
    analyst_count: int
    target_mean: Optional[float]
    target_high: Optional[float]
    target_low: Optional[float]
    upside_pct: Optional[float]
    conflict_notes: str = ""
    # Fundamentals
    pe_trailing: Optional[float] = None
    pe_forward: Optional[float] = None
    revenue_growth: Optional[float] = None       # e.g. 0.12 = 12% YoY
    earnings_growth: Optional[float] = None
    profit_margin: Optional[float] = None
    debt_to_equity: Optional[float] = None
    free_cashflow: Optional[float] = None
    return_on_equity: Optional[float] = None
    beta: Optional[float] = None
    short_float_pct: Optional[float] = None      # % of float sold short
    short_ratio: Optional[float] = None          # days to cover
    inst_ownership_pct: Optional[float] = None   # % held by institutions
    insider_ownership_pct: Optional[float] = None
    sp500_52w_change: Optional[float] = None     # stock's 52w change vs S&P 500
    stock_52w_change: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    long_business_summary: Optional[str] = None
    fundamentals_json: str = field(default_factory=lambda: "{}")


def _finnhub_client() -> Optional[finnhub.Client]:
    key = os.getenv("FINNHUB_API_KEY", "")
    return finnhub.Client(api_key=key) if key else None


def _safe_float(info: dict, *keys) -> Optional[float]:
    for k in keys:
        v = info.get(k)
        if v is not None:
            try:
                f = float(v)
                return f if f != 0 else None
            except (TypeError, ValueError):
                pass
    return None


def _yf_analyst(ticker: str, prefetched=None) -> dict:
    try:
        info = prefetched.info if prefetched is not None else yf.Ticker(ticker).info
        rec = (info.get("recommendationKey") or "").upper().replace("_", " ")
        label_map = {
            "STRONG BUY": "STRONG BUY", "BUY": "BUY", "HOLD": "HOLD",
            "SELL": "SELL", "STRONG SELL": "STRONG SELL",
            "UNDERPERFORM": "SELL", "OUTPERFORM": "BUY", "OVERWEIGHT": "BUY",
            "UNDERWEIGHT": "SELL", "NEUTRAL": "HOLD", "MARKET PERFORM": "HOLD",
        }
        consensus = label_map.get(rec, "N/A")

        # Fundamentals — extracted from the same info dict we already fetched
        fundamentals = {
            "pe_trailing": _safe_float(info, "trailingPE"),
            "pe_forward": _safe_float(info, "forwardPE"),
            "revenue_growth": _safe_float(info, "revenueGrowth"),
            "earnings_growth": _safe_float(info, "earningsGrowth"),
            "profit_margin": _safe_float(info, "profitMargins"),
            "debt_to_equity": _safe_float(info, "debtToEquity"),
            "free_cashflow": _safe_float(info, "freeCashflow"),
            "return_on_equity": _safe_float(info, "returnOnEquity"),
            "beta": _safe_float(info, "beta"),
            "short_float_pct": _safe_float(info, "shortPercentOfFloat"),
            "short_ratio": _safe_float(info, "shortRatio"),
            "inst_ownership_pct": _safe_float(info, "heldPercentInstitutions"),
            "insider_ownership_pct": _safe_float(info, "heldPercentInsiders"),
            "sp500_52w_change": _safe_float(info, "SandP52WeekChange"),
            "stock_52w_change": _safe_float(info, "52WeekChange", "fiftyTwoWeekChange"),
            "dividend_yield": _safe_float(info, "dividendYield", "trailingAnnualDividendYield"),
            "market_cap": _safe_float(info, "marketCap"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "long_business_summary": info.get("longBusinessSummary"),
        }

        return {
            "consensus": consensus,
            "analyst_count": int(info.get("numberOfAnalystOpinions") or 0),
            "target_mean": _safe_float(info, "targetMeanPrice"),
            "target_high": _safe_float(info, "targetHighPrice"),
            "target_low": _safe_float(info, "targetLowPrice"),
            "fundamentals": fundamentals,
        }
    except Exception:
        return {
            "consensus": "N/A", "analyst_count": 0,
            "target_mean": None, "target_high": None, "target_low": None,
            "fundamentals": {},
        }


def _fh_analyst(ticker: str) -> Optional[str]:
    client = _finnhub_client()
    if not client:
        return None
    try:
        recs = client.recommendation_trends(ticker) or []
        if not recs:
            return None
        latest = recs[0]
        sb = latest.get("strongBuy", 0)
        b = latest.get("buy", 0)
        h = latest.get("hold", 0)
        s = latest.get("sell", 0)
        ss = latest.get("strongSell", 0)
        total = sb + b + h + s + ss
        if total == 0:
            return "N/A"
        if (sb + b) / total >= 0.6:
            return "BUY"
        if (s + ss) / total >= 0.6:
            return "SELL"
        return "HOLD"
    except Exception:
        return None


async def fetch_analyst_data(ticker: str, current_price: float = 0.0, prefetched=None) -> AnalystData:
    loop = asyncio.get_event_loop()
    yf_result, fh_consensus = await asyncio.gather(
        loop.run_in_executor(None, _yf_analyst, ticker, prefetched),
        loop.run_in_executor(None, _fh_analyst, ticker),
    )

    conflict = ""
    if fh_consensus and fh_consensus != "N/A" and yf_result["consensus"] != "N/A":
        if fh_consensus != yf_result["consensus"]:
            conflict = f"Analyst conflict: yfinance={yf_result['consensus']} vs Finnhub={fh_consensus}."

    upside = None
    if current_price and yf_result["target_mean"]:
        upside = round((yf_result["target_mean"] - current_price) / current_price * 100, 1)

    f = yf_result.get("fundamentals", {})
    return AnalystData(
        consensus=yf_result["consensus"],
        analyst_count=yf_result["analyst_count"],
        target_mean=yf_result["target_mean"],
        target_high=yf_result["target_high"],
        target_low=yf_result["target_low"],
        upside_pct=upside,
        conflict_notes=conflict,
        pe_trailing=f.get("pe_trailing"),
        pe_forward=f.get("pe_forward"),
        revenue_growth=f.get("revenue_growth"),
        earnings_growth=f.get("earnings_growth"),
        profit_margin=f.get("profit_margin"),
        debt_to_equity=f.get("debt_to_equity"),
        free_cashflow=f.get("free_cashflow"),
        return_on_equity=f.get("return_on_equity"),
        beta=f.get("beta"),
        short_float_pct=f.get("short_float_pct"),
        short_ratio=f.get("short_ratio"),
        inst_ownership_pct=f.get("inst_ownership_pct"),
        insider_ownership_pct=f.get("insider_ownership_pct"),
        sp500_52w_change=f.get("sp500_52w_change"),
        stock_52w_change=f.get("stock_52w_change"),
        dividend_yield=f.get("dividend_yield"),
        market_cap=f.get("market_cap"),
        sector=f.get("sector"),
        industry=f.get("industry"),
        long_business_summary=f.get("long_business_summary"),
        fundamentals_json=json.dumps(f),
    )
