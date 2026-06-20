from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import CopilotDecision, SimulationPortfolio, SimulationTrade
from routers.auth import get_current_user
from schemas import CopilotDecisionRequest, SimulationPortfolioOut, SimulationTradeOut

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.get("/{mode}/portfolio", response_model=list[SimulationPortfolioOut])
def get_portfolio(mode: str, id_token: str, db: Session = Depends(get_db)):
    if mode not in ("autopilot", "copilot"):
        raise HTTPException(status_code=400, detail="mode must be autopilot or copilot")
    user = get_current_user(id_token, db)
    return db.query(SimulationPortfolio).filter(
        SimulationPortfolio.user_email == user.email,
        SimulationPortfolio.mode == mode,
    ).all()


@router.get("/{mode}/trades", response_model=list[SimulationTradeOut])
def get_trades(mode: str, id_token: str, db: Session = Depends(get_db)):
    if mode not in ("autopilot", "copilot"):
        raise HTTPException(status_code=400, detail="mode must be autopilot or copilot")
    user = get_current_user(id_token, db)
    return (
        db.query(SimulationTrade)
        .filter(SimulationTrade.user_email == user.email, SimulationTrade.mode == mode)
        .order_by(SimulationTrade.trade_date.desc())
        .limit(50)
        .all()
    )


@router.post("/copilot/decide")
def record_copilot_decision(
    id_token: str,
    body: CopilotDecisionRequest,
    db: Session = Depends(get_db),
):
    if body.decision not in ("approve", "skip", "override"):
        raise HTTPException(status_code=400, detail="decision must be approve, skip, or override")
    user = get_current_user(id_token, db)
    decision = CopilotDecision(
        user_email=user.email,
        analysis_id=body.analysis_id,
        ticker=body.ticker.upper(),
        decision=body.decision,
        override_action=body.override_action,
        override_price=body.override_price,
    )
    db.add(decision)
    db.commit()
    return {"status": "recorded", "decision": body.decision}
