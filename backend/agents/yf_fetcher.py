"""
Single yfinance fetch for a ticker — call once, share across all agents.
Prevents Yahoo Finance 429s from parallel agent calls hitting the same ticker.
"""
import time
import logging
from dataclasses import dataclass
from typing import Optional
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class YFData:
    info: dict
    history: pd.DataFrame
    news: list
    calendar: Optional[dict]


def fetch_yf_data(ticker: str, retries: int = 3, backoff: float = 10.0) -> YFData:
    for attempt in range(retries):
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            if not info or info.get("trailingPegRatio") is None and not info.get("currentPrice") and not info.get("regularMarketPrice"):
                raise ValueError("Empty or invalid info response from yfinance")
            try:
                hist = t.history(period="1y")
            except Exception:
                hist = pd.DataFrame()
            try:
                news = t.news or []
            except Exception:
                news = []
            try:
                calendar = t.calendar
            except Exception:
                calendar = None
            return YFData(info=info, history=hist, news=news, calendar=calendar)
        except Exception as e:
            if attempt < retries - 1:
                wait = backoff * (attempt + 1)
                logger.warning(f"[{ticker}] yfinance attempt {attempt + 1} failed ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
