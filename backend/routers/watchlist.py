import asyncio
import logging
import re
import requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import WatchlistItem
from routers.auth import get_current_user
from schemas import WatchlistAddRequest, WatchlistItemOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

_TICKER_RE = re.compile(r'^[A-Z]{1,5}([.\-][A-Z]{1,2})?$')

_LEVERAGED_KEYWORDS = {"2x", "3x", "ultra", "ultrashort", "ultralong", "leveraged", "daily bull", "daily bear", "proshares", "direxion", "microsectors"}

def _detect_leveraged(ticker: str) -> bool:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        name = (info.get("longName") or info.get("shortName") or "").lower()
        return any(kw in name for kw in _LEVERAGED_KEYWORDS)
    except Exception:
        return False


@router.get("/search")
def search_tickers(q: str, id_token: str, db: Session = Depends(get_db)):
    get_current_user(id_token, db)
    if len(q.strip()) < 1:
        return []
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": q, "quotesCount": 8, "newsCount": 0, "enableFuzzyQuery": True},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        quotes = r.json().get("quotes", [])
        return [
            {
                "ticker": item["symbol"],
                "name": item.get("longname") or item.get("shortname") or "",
                "exchange": item.get("exchange") or "",
                "type": item.get("quoteType") or "",
            }
            for item in quotes
            if item.get("symbol") and item.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND")
        ]
    except Exception:
        return []


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(id_token: str, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    items = db.query(WatchlistItem).filter(WatchlistItem.user_email == user.email).all()
    return items


def _run_analysis_for_ticker(ticker: str, is_leveraged: bool, sector: str, company_name: str):
    """Fire-and-forget background task — runs full pipeline for a single new ticker."""
    from services.nightly_runner import _analyze_single_ticker
    session = SessionLocal()
    try:
        asyncio.run(_analyze_single_ticker(ticker, is_leveraged, sector, company_name, session))
        logger.info(f"[{ticker}] Background analysis triggered by watchlist add — complete.")
    except Exception as e:
        logger.error(f"[{ticker}] Background analysis failed: {e}")
    finally:
        session.close()


@router.post("", response_model=WatchlistItemOut)
def add_to_watchlist(
    id_token: str,
    body: WatchlistAddRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = get_current_user(id_token, db)
    ticker = body.ticker.upper().strip()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(status_code=400, detail=f"Invalid ticker format: {ticker}")
    existing = db.query(WatchlistItem).filter(
        WatchlistItem.user_email == user.email,
        WatchlistItem.ticker == ticker,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"{ticker} already in watchlist.")
    is_leveraged = _detect_leveraged(ticker)
    item = WatchlistItem(
        user_email=user.email,
        ticker=ticker,
        company_name=body.company_name,
        sector=body.sector,
        is_leveraged=is_leveraged,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # Auto-analyze on add — controlled by AUTO_ANALYZE_ON_ADD env var (default: off)
    import os
    if os.getenv("AUTO_ANALYZE_ON_ADD", "false").lower() == "true":
        background_tasks.add_task(
            _run_analysis_for_ticker,
            ticker, is_leveraged, body.sector or "", body.company_name or ticker,
        )
        logger.info(f"[{ticker}] Added to watchlist — background analysis queued.")
    return item


@router.delete("/{ticker}")
def remove_from_watchlist(ticker: str, id_token: str, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    item = db.query(WatchlistItem).filter(
        WatchlistItem.user_email == user.email,
        WatchlistItem.ticker == ticker.upper(),
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ticker not in watchlist.")
    db.delete(item)
    db.commit()
    return {"deleted": ticker.upper()}
