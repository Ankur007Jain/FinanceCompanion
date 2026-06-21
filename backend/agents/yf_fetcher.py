"""
Single yfinance fetch for a ticker — call once, share across all agents.
Checks DB cache first; only hits Yahoo Finance if no cache exists for today.
"""
import json
import time
import logging
from dataclasses import dataclass
from datetime import date
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


def _serialize(yf_data: YFData) -> dict:
    return {
        "info": yf_data.info,
        "history": yf_data.history.to_json(orient="split", date_format="iso") if not yf_data.history.empty else "{}",
        "news": yf_data.news,
        "calendar": yf_data.calendar,
    }


def _deserialize(row) -> YFData:
    info = json.loads(row.info_json or "{}")
    try:
        hist_raw = json.loads(row.history_json or "{}")
        history = pd.read_json(json.dumps(hist_raw), orient="split") if hist_raw else pd.DataFrame()
    except Exception:
        history = pd.DataFrame()
    news = json.loads(row.news_json or "[]")
    calendar = json.loads(row.calendar_json or "null")
    return YFData(info=info, history=history, news=news, calendar=calendar)


def _fetch_from_api(ticker: str, retries: int = 3, backoff: float = 10.0) -> YFData:
    for attempt in range(retries):
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            if not info or (not info.get("currentPrice") and not info.get("regularMarketPrice")):
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


def fetch_yf_data(ticker: str, db=None, retries: int = 3, backoff: float = 10.0) -> YFData:
    """
    Returns YFData for ticker. If db is provided, checks the market_data_cache table first.
    On cache miss, fetches from yfinance and saves to cache.
    """
    today = date.today()

    if db is not None:
        from models import MarketDataCache
        cached = db.query(MarketDataCache).filter(
            MarketDataCache.ticker == ticker,
            MarketDataCache.cache_date == today,
        ).first()

        if cached:
            logger.info(f"[{ticker}] Using cached market data from DB (fetched earlier today).")
            return _deserialize(cached)

    logger.info(f"[{ticker}] Fetching fresh data from yfinance...")
    data = _fetch_from_api(ticker, retries=retries, backoff=backoff)

    if db is not None:
        try:
            from models import MarketDataCache
            serialized = _serialize(data)
            entry = MarketDataCache(
                ticker=ticker,
                cache_date=today,
                info_json=json.dumps(serialized["info"]),
                history_json=serialized["history"],
                news_json=json.dumps(serialized["news"]),
                calendar_json=json.dumps(serialized["calendar"]),
            )
            db.merge(entry)
            db.commit()
            logger.info(f"[{ticker}] Market data cached to DB.")
        except Exception as e:
            logger.warning(f"[{ticker}] Failed to cache market data: {e}")

    return data
