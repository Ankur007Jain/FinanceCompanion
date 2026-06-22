from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import StockAnalysis, WatchlistItem
from routers.auth import get_current_user
from schemas import DigestItem, StockAnalysisOut

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/digest", response_model=list[DigestItem])
def get_digest(id_token: str, db: Session = Depends(get_db)):
    """Today's digest for all stocks in the user's watchlist."""
    user = get_current_user(id_token, db)
    watchlist = db.query(WatchlistItem).filter(WatchlistItem.user_email == user.email).all()
    today = date.today()
    result = []
    for item in watchlist:
        analysis = db.query(StockAnalysis).filter(
            StockAnalysis.ticker == item.ticker,
            StockAnalysis.analysis_date == today,
        ).first()
        result.append(DigestItem(
            ticker=item.ticker,
            company_name=item.company_name,
            is_leveraged=item.is_leveraged or False,
            analysis=StockAnalysisOut.model_validate(analysis) if analysis else None,
        ))
    return result


@router.get("/{ticker}/latest", response_model=StockAnalysisOut)
def get_latest(ticker: str, id_token: str, db: Session = Depends(get_db)):
    get_current_user(id_token, db)
    analysis = db.query(StockAnalysis).filter(
        StockAnalysis.ticker == ticker.upper(),
    ).order_by(StockAnalysis.analysis_date.desc()).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this ticker.")
    return analysis


@router.get("/important", response_model=list[StockAnalysisOut])
def get_important(id_token: str, days: int = 30, db: Session = Depends(get_db)):
    """Important-day analyses across the user's watchlist (verdict reversals, earnings, catalysts)."""
    user = get_current_user(id_token, db)
    tickers = [
        row.ticker
        for row in db.query(WatchlistItem).filter(WatchlistItem.user_email == user.email).all()
    ]
    if not tickers:
        return []
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=days)
    return (
        db.query(StockAnalysis)
        .filter(
            StockAnalysis.ticker.in_(tickers),
            StockAnalysis.is_important_day == True,  # noqa: E712
            StockAnalysis.analysis_date >= cutoff,
        )
        .order_by(StockAnalysis.analysis_date.desc())
        .limit(50)
        .all()
    )


@router.get("/{ticker}/history", response_model=list[StockAnalysisOut])
def get_history(ticker: str, id_token: str, days: int = 30, db: Session = Depends(get_db)):
    get_current_user(id_token, db)
    rows = (
        db.query(StockAnalysis)
        .filter(StockAnalysis.ticker == ticker.upper())
        .order_by(StockAnalysis.analysis_date.desc())
        .limit(days)
        .all()
    )
    return rows
