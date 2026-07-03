from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Feedback
from routers.auth import get_current_user
from schemas import FeedbackCreate, FeedbackOut

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut)
def submit_feedback(body: FeedbackCreate, id_token: str, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    fb = Feedback(user_email=user.email, message=body.message)
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb
