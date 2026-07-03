from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Feedback, StockAnalysis, TickerControl, User, WatchlistItem
from routers.auth import get_current_user
from schemas import (
    AdminNightlyCostOut,
    AdminUserOut,
    AdminUserUpdate,
    FeedbackOut,
    TickerControlOut,
    TickerControlUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(id_token: str, db: Session) -> User:
    user = get_current_user(id_token, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


@router.get("/users", response_model=list[AdminUserOut])
def list_users(id_token: str, db: Session = Depends(get_db)):
    require_admin(id_token, db)
    users = db.query(User).order_by(User.created_at.desc()).all()
    watchlists = db.query(WatchlistItem.user_email, WatchlistItem.ticker).all()
    tickers_by_user: dict[str, list[str]] = {}
    for email, ticker in watchlists:
        tickers_by_user.setdefault(email, []).append(ticker)

    return [
        AdminUserOut(
            email=u.email,
            name=u.name,
            tier=u.tier,
            is_admin=u.is_admin,
            tokens_used=u.tokens_used,
            created_at=u.created_at,
            tickers=sorted(tickers_by_user.get(u.email, [])),
        )
        for u in users
    ]


@router.patch("/users/{email}", response_model=AdminUserOut)
def update_user(email: str, body: AdminUserUpdate, id_token: str, db: Session = Depends(get_db)):
    require_admin(id_token, db)
    target = db.get(User, email)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if body.is_admin is not None:
        target.is_admin = body.is_admin
    if body.tier is not None:
        target.tier = body.tier
    db.commit()
    db.refresh(target)
    tickers = [w.ticker for w in db.query(WatchlistItem).filter(WatchlistItem.user_email == email).all()]
    return AdminUserOut(
        email=target.email, name=target.name, tier=target.tier, is_admin=target.is_admin,
        tokens_used=target.tokens_used, created_at=target.created_at, tickers=sorted(tickers),
    )


@router.get("/tickers", response_model=list[TickerControlOut])
def list_tickers(id_token: str, db: Session = Depends(get_db)):
    require_admin(id_token, db)
    all_tickers = {t[0] for t in db.query(WatchlistItem.ticker).distinct().all()}
    controls = {c.ticker: c for c in db.query(TickerControl).all()}

    return [
        TickerControlOut(
            ticker=t,
            analysis_enabled=controls[t].analysis_enabled if t in controls else True,
            disabled_by=controls[t].disabled_by if t in controls else None,
            disabled_at=controls[t].disabled_at if t in controls else None,
        )
        for t in sorted(all_tickers)
    ]


@router.patch("/tickers/{ticker}", response_model=TickerControlOut)
def set_ticker_control(ticker: str, body: TickerControlUpdate, id_token: str, db: Session = Depends(get_db)):
    admin = require_admin(id_token, db)
    ticker = ticker.upper()
    control = db.get(TickerControl, ticker)
    if not control:
        control = TickerControl(ticker=ticker)
        db.add(control)
    control.analysis_enabled = body.analysis_enabled
    control.disabled_by = None if body.analysis_enabled else admin.email
    control.disabled_at = None if body.analysis_enabled else datetime.utcnow()
    db.commit()
    db.refresh(control)
    return control


@router.get("/feedback", response_model=list[FeedbackOut])
def list_feedback(id_token: str, db: Session = Depends(get_db)):
    require_admin(id_token, db)
    return db.query(Feedback).order_by(Feedback.created_at.desc()).all()


@router.get("/costs", response_model=list[AdminNightlyCostOut])
def list_nightly_costs(id_token: str, days: int = 14, db: Session = Depends(get_db)):
    require_admin(id_token, db)
    rows = (
        db.query(StockAnalysis)
        .filter(
            (StockAnalysis.cost_usd.isnot(None)) | (StockAnalysis.simple_fields_cost_usd.isnot(None))
        )
        .order_by(StockAnalysis.analysis_date.desc())
        .limit(days * 50)
        .all()
    )
    return [
        AdminNightlyCostOut(
            ticker=r.ticker,
            analysis_date=r.analysis_date,
            gemini_tokens_input=r.tokens_input,
            gemini_tokens_output=r.tokens_output,
            gemini_cost_usd=r.cost_usd,
            simple_fields_tokens_input=r.simple_fields_tokens_input,
            simple_fields_tokens_output=r.simple_fields_tokens_output,
            simple_fields_cost_usd=r.simple_fields_cost_usd,
        )
        for r in rows
    ]
