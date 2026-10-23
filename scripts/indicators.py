"""
Standard (Wilder) RSI — the definition pandas_ta, backend/agents/price_agent.py, brokers and
charting sites use.

nightly_fetch.py computed RSI from simple 14-day rolling means (Cutler's RSI) until 2026-10-23.
Over May–Oct 2026 that ran a median 5.6pt (up to ~40pt) off the standard, flagged oversold/
overbought ~3x as often, and on the ~15% of days the two disagreed about the signal score's
"RSI < 50" point, the standard one was right both ways (21d excess vs universe: -1.09% when
only the old one gave the point, +0.87% when only the standard one did).

Plain pandas rather than pandas_ta: a pandas_ta import failure once nulled RSI for an entire
nightly run (#132).
"""
import pandas as pd


def wilder_rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False).mean()
    total = gain + loss
    return (100 * gain / total).where(total != 0, 50.0)
