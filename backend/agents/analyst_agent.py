"""
Analyst Agent — fetches analyst consensus and price targets from yfinance (primary)
and Finnhub (secondary), then cross-validates.
"""
import os
import asyncio
from dataclasses import dataclass
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
    upside_pct: Optional[float]  # vs current price
    conflict_notes: str = ""


def _finnhub_client() -> Optional[finnhub.Client]:
    key = os.getenv("FINNHUB_API_KEY", "")
    return finnhub.Client(api_key=key) if key else None


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
        return {
            "consensus": consensus,
            "analyst_count": int(info.get("numberOfAnalystOpinions") or 0),
            "target_mean": float(info.get("targetMeanPrice") or 0) or None,
            "target_high": float(info.get("targetHighPrice") or 0) or None,
            "target_low": float(info.get("targetLowPrice") or 0) or None,
        }
    except Exception:
        return {"consensus": "N/A", "analyst_count": 0, "target_mean": None, "target_high": None, "target_low": None}


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
        bull = sb + b
        bear = s + ss
        if bull / total >= 0.6:
            return "BUY"
        if bear / total >= 0.6:
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

    return AnalystData(
        consensus=yf_result["consensus"],
        analyst_count=yf_result["analyst_count"],
        target_mean=yf_result["target_mean"],
        target_high=yf_result["target_high"],
        target_low=yf_result["target_low"],
        upside_pct=upside,
        conflict_notes=conflict,
    )
