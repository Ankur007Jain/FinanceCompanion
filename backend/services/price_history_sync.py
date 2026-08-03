"""
Price history sync — backfills a symbol's daily OHLCV once, then only fetches bars
since the last sync on every call after that. Replaces the old pattern of pulling a
full multi-year yfinance history every night for every ticker (and, for shared symbols
like "^GSPC" or a sector ETF, redundantly once per ticker that references them).

symbol is a ticker, an index ("^GSPC"), or a sector ETF — same table, same sync logic.
"""
import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import PriceHistory

logger = logging.getLogger(__name__)

_BACKFILL_YEARS = 5  # matches nightly_fetch.py's existing period="5y" — covers both 1y technicals and 5y change


def _rows_from_history(symbol: str, hist: pd.DataFrame) -> list[dict]:
    if hist.empty:
        return []
    rows = []
    for idx, row in hist.iterrows():
        rows.append({
            "symbol": symbol,
            "date": idx.date(),
            "open": float(row["Open"]) if pd.notna(row["Open"]) else None,
            "high": float(row["High"]) if pd.notna(row["High"]) else None,
            "low": float(row["Low"]) if pd.notna(row["Low"]) else None,
            "close": float(row["Close"]) if pd.notna(row["Close"]) else None,
            "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else None,
            "stock_split": float(row["Stock Splits"]) if "Stock Splits" in row and pd.notna(row["Stock Splits"]) else 0.0,
        })
    return rows


def _write_rows(db: Session, symbol: str, rows: list[dict], overwrite: bool = False) -> None:
    """Up to 6 nightly batches run concurrently (see .github/workflows/nightly.yml), and
    every batch's first ticker in a shared sector/index tends to request the same symbol
    (e.g. "^GSPC") at nearly the same moment — most acutely on the very first backfill,
    when literally every batch races to backfill it for the first time. merge()+commit()
    isn't atomic across sessions, so a concurrent writer can trip a duplicate-PK
    IntegrityError here; that's a benign "someone else already wrote this" race, not a
    real failure — roll back and move on. sync_and_get_bars re-reads fresh state after
    this call regardless of which concurrent writer's commit actually won."""
    if overwrite:
        db.query(PriceHistory).filter(PriceHistory.symbol == symbol).delete()
    for r in rows:
        db.merge(PriceHistory(**r))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info(f"[{symbol}] Concurrent write detected during commit — rolled back, another sync already covered this.")


def _backfill(db: Session, symbol: str, overwrite: bool = False) -> None:
    hist = yf.Ticker(symbol).history(period=f"{_BACKFILL_YEARS}y")
    rows = _rows_from_history(symbol, hist)
    _write_rows(db, symbol, rows, overwrite=overwrite)
    logger.info(f"[{symbol}] Backfilled {len(rows)} rows ({'overwrite' if overwrite else 'fresh'}).")


def _incremental(db: Session, symbol: str, since: date) -> bool:
    """Fetches bars from `since` to today. Returns True if a split was detected
    (caller should then do a full re-backfill — every prior close needs rescaling)."""
    hist = yf.Ticker(symbol).history(start=since)
    rows = _rows_from_history(symbol, hist)
    if not rows:
        return False
    split_detected = any(r["stock_split"] not in (0.0, None) for r in rows)
    if split_detected:
        return True
    _write_rows(db, symbol, rows)
    logger.info(f"[{symbol}] Appended {len(rows)} new row(s).")
    return False


def sync_and_get_bars(symbol: str, db: Session) -> list[dict]:
    today = date.today()
    latest = db.query(func.max(PriceHistory.date)).filter(PriceHistory.symbol == symbol).scalar()

    if latest is None:
        _backfill(db, symbol)
    elif latest < today:
        if today.day <= 3:
            # First sync of a new day, within the first few days of the month — do a full
            # refresh instead of a plain append, to correct dividend-adjustment drift that
            # accumulates on every ex-dividend date. Resyncing on every dividend would erode
            # most of the savings this design exists for, so it's batched into this monthly
            # pass instead. Gated on the day-transition (not "already synced today, and it's
            # day<=3") so a second ticker sharing this symbol later the same day is still a
            # pure cache hit below, not a repeated full backfill.
            _backfill(db, symbol, overwrite=True)
        else:
            split_detected = _incremental(db, symbol, since=latest + timedelta(days=1))
            if split_detected:
                logger.info(f"[{symbol}] Split detected in incremental fetch — forcing full re-backfill.")
                _backfill(db, symbol, overwrite=True)
    # else: latest == today — already synced, pure cache hit. This is what collapses
    # repeated ^GSPC/sector-ETF fetches across every ticker in the same nightly batch to one.

    bars = (
        db.query(PriceHistory)
        .filter(PriceHistory.symbol == symbol)
        .order_by(PriceHistory.date)
        .all()
    )
    return [
        {
            "date": str(b.date),
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ]
