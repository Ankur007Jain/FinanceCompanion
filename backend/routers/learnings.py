from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import UserLearning
from routers.auth import get_current_user

router = APIRouter(prefix="/learnings", tags=["learnings"])


class LearningOut(BaseModel):
    id: str
    learning: str
    ticker: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LearningUpdate(BaseModel):
    learning: str


@router.get("", response_model=list[LearningOut])
def list_learnings(id_token: str, db: Session = Depends(get_db)):
    """Everything saved for this user — global and ticker-scoped together, most
    recent first. Powers the settings page where a user can review/edit/delete what
    the AI actually has on file, the same real data build_user_learnings_block and
    build_ticker_dossier read from."""
    user = get_current_user(id_token, db)
    return (
        db.query(UserLearning)
        .filter(UserLearning.user_email == user.email)
        .order_by(UserLearning.created_at.desc())
        .all()
    )


@router.patch("/{learning_id}", response_model=LearningOut)
def update_learning(learning_id: str, id_token: str, body: LearningUpdate, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    row = db.get(UserLearning, learning_id)
    if not row or row.user_email != user.email:
        raise HTTPException(status_code=404, detail="Learning not found.")
    text = body.learning.strip()
    if not text:
        raise HTTPException(status_code=422, detail="learning cannot be empty.")
    row.learning = text
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{learning_id}")
def delete_learning(learning_id: str, id_token: str, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    row = db.get(UserLearning, learning_id)
    if not row or row.user_email != user.email:
        raise HTTPException(status_code=404, detail="Learning not found.")
    db.delete(row)
    db.commit()
    return {"deleted": learning_id}
