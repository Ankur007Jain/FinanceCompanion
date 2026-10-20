"""
Regular-session price and day change for one ticker, from yfinance's `info` dict.

Why not `fast_info`: nightly runs land 08:00-11:00 UTC, which is US pre-market. In that
window `fast_info.previous_close` is unreliable — often equal to the last close (a fake
0.0% day) or something else entirely (STX on 2026-10-14 came out +3.35% on a -4.50% day).
`info`'s regularMarketPrice / regularMarketPreviousClose describe the same completed
session and were correct in every row checked, so they're the source of truth here.
Shared with scripts/backfill_day_change.py so stored history and new rows agree.
"""


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def regular_session_quote(info: dict, fallback_price=None):
    """Returns (price, previous_close, change_pct). change_pct is None — never 0 — when
    there's no trustworthy previous close, so a missing value can't masquerade as a flat day."""
    info = info or {}
    price = _num(info.get("regularMarketPrice")) or _num(info.get("currentPrice")) or _num(fallback_price)
    prev = _num(info.get("regularMarketPreviousClose")) or _num(info.get("previousClose"))
    if price is None or prev is None:
        return price, prev, None
    return price, prev, (price - prev) / prev * 100
