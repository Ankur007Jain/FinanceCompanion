from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import WatchlistItem
from routers.auth import get_current_user
from schemas import WatchlistAddRequest, WatchlistItemOut

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

_LEVERAGED_KEYWORDS = {"2x", "3x", "ultra", "ultrashort", "ultralong", "leveraged", "daily bull", "daily bear", "proshares", "direxion", "microsectors"}

def _detect_leveraged(ticker: str) -> bool:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        name = (info.get("longName") or info.get("shortName") or "").lower()
        return any(kw in name for kw in _LEVERAGED_KEYWORDS)
    except Exception:
        return False


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(id_token: str, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    items = db.query(WatchlistItem).filter(WatchlistItem.user_email == user.email).all()
    return items


@router.post("", response_model=WatchlistItemOut)
def add_to_watchlist(id_token: str, body: WatchlistAddRequest, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    ticker = body.ticker.upper().strip()
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
