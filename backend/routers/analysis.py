from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import StockAnalysis, WatchlistItem
from routers.auth import get_current_user
from schemas import DigestItem, StockAnalysisOut, ImportantFlag, ReportDayOut

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/digest", response_model=list[DigestItem])
def get_digest(id_token: str, db: Session = Depends(get_db)):
    """Digest for all stocks in the user's watchlist — most recent analysis within 7 days."""
    user = get_current_user(id_token, db)
    watchlist = db.query(WatchlistItem).filter(WatchlistItem.user_email == user.email).all()
    cutoff = date.today() - timedelta(days=7)
    result = []
    for item in watchlist:
        analysis = (
            db.query(StockAnalysis)
            .filter(
                StockAnalysis.ticker == item.ticker,
                StockAnalysis.analysis_date >= cutoff,
            )
            .order_by(StockAnalysis.analysis_date.desc())
            .first()
        )
        result.append(DigestItem(
            ticker=item.ticker,
            company_name=item.company_name,
            is_leveraged=item.is_leveraged or False,
            analysis=StockAnalysisOut.model_validate(analysis) if analysis else None,
        ))
    return result


@router.get("/reports", response_model=list[ReportDayOut])
def get_reports(id_token: str, limit: int = 7, db: Session = Depends(get_db)):
    """Last N nightly report summaries for the user's watchlist, newest first."""
    user = get_current_user(id_token, db)
    watchlist_tickers = [
        row.ticker
        for row in db.query(WatchlistItem).filter(WatchlistItem.user_email == user.email).all()
    ]
    if not watchlist_tickers:
        return []

    dates = (
        db.query(StockAnalysis.analysis_date)
        .filter(StockAnalysis.ticker.in_(watchlist_tickers))
        .distinct()
        .order_by(StockAnalysis.analysis_date.desc())
        .limit(limit)
        .all()
    )

    result = []
    for (report_date,) in dates:
        analyses = (
            db.query(StockAnalysis)
            .filter(
                StockAnalysis.ticker.in_(watchlist_tickers),
                StockAnalysis.analysis_date == report_date,
            )
            .all()
        )
        by_verdict: dict[str, list[str]] = {}
        important_flags: list[ImportantFlag] = []
        for a in analyses:
            by_verdict.setdefault(a.verdict, []).append(a.ticker)
            if a.is_important_day:
                important_flags.append(ImportantFlag(
                    ticker=a.ticker,
                    verdict=a.verdict,
                    importance_reason=a.importance_reason,
                ))
        result.append(ReportDayOut(
            report_date=str(report_date),
            analyzed_count=len(analyses),
            total_watchlist=len(watchlist_tickers),
            by_verdict=by_verdict,
            important_flags=important_flags,
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
