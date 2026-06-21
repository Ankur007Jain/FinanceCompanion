"""
Event Agent — fetches upcoming earnings dates from yfinance and Finnhub,
plus a hardcoded Fed calendar. Returns a list of event dicts.
"""
import os
import asyncio
from datetime import date, timedelta
from typing import Optional

import finnhub
import yfinance as yf


def _finnhub_client() -> Optional[finnhub.Client]:
    key = os.getenv("FINNHUB_API_KEY", "")
    return finnhub.Client(api_key=key) if key else None


def _yf_earnings(ticker: str, prefetched=None) -> Optional[str]:
    try:
        cal = prefetched.calendar if prefetched is not None else yf.Ticker(ticker).calendar
        if cal is None:
            return None
        if hasattr(cal, "columns") and "Earnings Date" in cal.columns:
            val = cal["Earnings Date"].iloc[0]
            return str(val.date()) if hasattr(val, "date") else str(val)
        return None
    except Exception:
        return None


def _finnhub_earnings(ticker: str) -> Optional[str]:
    client = _finnhub_client()
    if not client:
        return None
    try:
        today = date.today().isoformat()
        three_months = (date.today() + timedelta(days=90)).isoformat()
        items = client.earnings_calendar(_from=today, to=three_months, symbol=ticker)
        earnings = (items or {}).get("earningsCalendar", [])
        if earnings:
            return earnings[0].get("date")
        return None
    except Exception:
        return None


def _upcoming_fed_dates() -> list[dict]:
    today = date.today()
    # Approximate FOMC meeting dates for 2026 — update annually
    fomc_dates = [
        date(2026, 7, 29), date(2026, 9, 16), date(2026, 11, 4), date(2026, 12, 16),
    ]
    upcoming = [d for d in fomc_dates if d >= today][:2]
    return [
        {"type": "macro", "date": str(d), "description": "FOMC Fed Rate Decision"}
        for d in upcoming
    ]


async def fetch_events(ticker: str, prefetched=None) -> list[dict]:
    loop = asyncio.get_event_loop()
    yf_date, fh_date = await asyncio.gather(
        loop.run_in_executor(None, _yf_earnings, ticker, prefetched),
        loop.run_in_executor(None, _finnhub_earnings, ticker),
    )

    events: list[dict] = []

    # Resolve earnings date — prefer yfinance, fall back to Finnhub
    earnings_date = yf_date or fh_date
    if earnings_date:
        events.append({
            "type": "earnings",
            "date": earnings_date,
            "description": f"{ticker} Earnings Report",
            "source": "yfinance" if yf_date else "finnhub",
        })

    events.extend(_upcoming_fed_dates())
    events.sort(key=lambda e: e["date"])
    return events
