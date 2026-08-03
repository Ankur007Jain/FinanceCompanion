"""
Client for the backend's /jobs/price-series endpoint — fetches a symbol's OHLCV
history via the accumulating price_history cache instead of pulling fresh from
yfinance every run. Split out of nightly_fetch.py so this transformation (the actual
regression risk of that change) is unit-testable on its own.
"""
import pandas as pd
import requests


def fetch_series(symbol: str, backend_url: str, job_secret: str) -> pd.DataFrame:
    """OHLCV history for `symbol` (ticker, "^GSPC", or a sector ETF), shaped to match
    yfinance's own history() output exactly: Open/High/Low/Close/Volume columns, a
    DatetimeIndex named "Date", ascending chronological order — so downstream code
    (RSI/MA/pivot calculations, the raw-history serializer) is unaffected by the switch."""
    r = requests.post(
        f"{backend_url}/jobs/price-series",
        params={"ticker": symbol, "x_job_secret": job_secret},
        timeout=30,
    )
    r.raise_for_status()
    df = pd.DataFrame(r.json()["bars"])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    )
    df.index.name = "Date"
    return df
