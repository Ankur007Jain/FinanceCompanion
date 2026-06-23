import os
from fastapi import APIRouter, Depends, HTTPException
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import TokenVerifyRequest, UserOut, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])


def verify_token(token: str) -> dict:
    # Test bypass — only active when TEST_MODE=true, never in production
    if os.getenv("TEST_MODE") == "true" and token.startswith("test-token-"):
        email = token[len("test-token-"):]
        if email:
            return {"email": email, "name": "Test User"}
        raise HTTPException(status_code=401, detail="Invalid test token format.")

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured.")
    try:
        return id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def get_current_user(token: str, db: Session) -> User:
    info = verify_token(token)
    email = info.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="No email in token.")
    user = db.get(User, email)
    if not user:
        user = User(email=email, name=info.get("name", ""))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.post("/verify", response_model=UserOut)
def verify(body: TokenVerifyRequest, db: Session = Depends(get_db)):
    user = get_current_user(body.id_token, db)
    return user


@router.patch("/me", response_model=UserOut)
def update_me(id_token: str, body: UserUpdate, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    if body.portfolio_size is not None:
        user.portfolio_size = body.portfolio_size
    db.commit()
    db.refresh(user)
    return user
