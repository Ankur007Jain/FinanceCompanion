"""
Price Agent — fetches OHLCV + technicals from yfinance (primary) and Finnhub (secondary).
Cross-validates both sources before returning. Computes RSI and moving averages in-house.
"""
import os
import asyncio
from dataclasses import dataclass, field
from typing import Optional

import finnhub
import pandas as pd
import yfinance as yf

try:
    import pandas_ta as ta
    _TA_AVAILABLE = True
except Exception:
    _TA_AVAILABLE = False


@dataclass
class PriceData:
    ticker: str
    current_price: float
    prev_close: float
    day_change_pct: float
    day_high: float
    day_low: float
    week_52_high: float
    week_52_low: float
    range_position_pct: float  # 0=at 52w low, 100=at 52w high
    volume: int
    avg_volume: int
    ma_50: float
    ma_200: float
    rsi: Optional[float]
    conflict_notes: str = ""


def _finnhub_client() -> Optional[finnhub.Client]:
    key = os.getenv("FINNHUB_API_KEY", "")
    return finnhub.Client(api_key=key) if key else None


def _compute_rsi(closes: pd.Series, period: int = 14) -> Optional[float]:
    if not _TA_AVAILABLE or len(closes) < period + 1:
        return None
    rsi_series = ta.rsi(closes, length=period)
    if rsi_series is None or rsi_series.empty:
        return None
    val = rsi_series.iloc[-1]
    return round(float(val), 2) if pd.notna(val) else None


def _yfinance_fetch(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info
    hist = t.history(period="1y")

    current = info.get("currentPrice") or info.get("regularMarketPrice", 0.0)
    prev = info.get("previousClose", 0.0)
    change_pct = ((current - prev) / prev * 100) if prev else 0.0

    w52h = info.get("fiftyTwoWeekHigh", 0.0)
    w52l = info.get("fiftyTwoWeekLow", 0.0)
    range_pos = ((current - w52l) / (w52h - w52l) * 100) if (w52h - w52l) > 0 else 50.0

    rsi = _compute_rsi(hist["Close"]) if not hist.empty else None

    return {
        "current_price": float(current or 0),
        "prev_close": float(prev or 0),
        "day_change_pct": round(change_pct, 2),
        "day_high": float(info.get("dayHigh") or info.get("regularMarketDayHigh") or current),
        "day_low": float(info.get("dayLow") or info.get("regularMarketDayLow") or current),
        "week_52_high": float(w52h),
        "week_52_low": float(w52l),
        "range_position_pct": round(range_pos, 1),
        "volume": int(info.get("volume") or info.get("regularMarketVolume") or 0),
        "avg_volume": int(info.get("averageVolume") or 0),
        "ma_50": float(info.get("fiftyDayAverage") or 0),
        "ma_200": float(info.get("twoHundredDayAverage") or 0),
        "rsi": rsi,
    }


def _finnhub_fetch(ticker: str) -> Optional[dict]:
    client = _finnhub_client()
    if not client:
        return None
    try:
        quote = client.quote(ticker)
        return {
            "current_price": float(quote.get("c", 0)),
            "prev_close": float(quote.get("pc", 0)),
            "day_high": float(quote.get("h", 0)),
            "day_low": float(quote.get("l", 0)),
        }
    except Exception:
        return None


def _cross_validate(primary: dict, secondary: Optional[dict]) -> str:
    if secondary is None:
        return "Finnhub unavailable — single source (yfinance)."
    p = primary["current_price"]
    s = secondary["current_price"]
    if p == 0 or s == 0:
        return "One source returned zero price — treat with caution."
    diff_pct = abs(p - s) / p * 100
    if diff_pct > 2:
        return f"Price conflict: yfinance ${p:.2f} vs Finnhub ${s:.2f} ({diff_pct:.1f}% gap) — using yfinance."
    return ""


async def fetch_price_data(ticker: str) -> PriceData:
    loop = asyncio.get_event_loop()
    primary, secondary = await asyncio.gather(
        loop.run_in_executor(None, _yfinance_fetch, ticker),
        loop.run_in_executor(None, _finnhub_fetch, ticker),
    )
    conflict = _cross_validate(primary, secondary)
    return PriceData(
        ticker=ticker,
        current_price=primary["current_price"],
        prev_close=primary["prev_close"],
        day_change_pct=primary["day_change_pct"],
        day_high=primary["day_high"],
        day_low=primary["day_low"],
        week_52_high=primary["week_52_high"],
        week_52_low=primary["week_52_low"],
        range_position_pct=primary["range_position_pct"],
        volume=primary["volume"],
        avg_volume=primary["avg_volume"],
        ma_50=primary["ma_50"],
        ma_200=primary["ma_200"],
        rsi=primary["rsi"],
        conflict_notes=conflict,
    )
