from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Conversation, Message
from routers.auth import get_current_user
from schemas import ConversationCreate, ConversationOut


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
def list_conversations(id_token: str, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    return (
        db.query(Conversation)
        .filter(Conversation.user_email == user.email)
        .order_by(Conversation.updated_at.desc())
        .limit(30)
        .all()
    )


@router.post("", response_model=ConversationOut)
def create_conversation(id_token: str, body: ConversationCreate, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    conv = Conversation(
        user_email=user.email,
        ticker=body.ticker.upper() if body.ticker else None,
        title=body.title,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: str, id_token: str, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.user_email != user.email:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conv


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(conversation_id: str, id_token: str, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.user_email != user.email:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )


@router.get("/by-ticker/{ticker}", response_model=list[ConversationOut])
def get_conversations_by_ticker(ticker: str, id_token: str, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    return (
        db.query(Conversation)
        .filter(
            Conversation.user_email == user.email,
            Conversation.ticker == ticker.upper(),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(20)
        .all()
    )


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str, id_token: str, db: Session = Depends(get_db)):
    user = get_current_user(id_token, db)
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.user_email != user.email:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    db.delete(conv)
    db.commit()
    return {"deleted": conversation_id}
