from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.conversation import Conversation, Message
from backend.app.controllers.auth_controller import get_current_user

router = APIRouter(prefix="/conversations", tags=["Conversations"])

class ConversationCreate(BaseModel):
    title: Optional[str] = "New Research Thread"
    document_id: Optional[str] = None

class MessageDTO(BaseModel):
    id: str
    role: str
    content: str
    retrieval_method: Optional[str] = None
    latency_ms: float = 0.0
    created_at: datetime

    model_config = {"from_attributes": True}

class ConversationResponse(BaseModel):
    id: str
    title: str
    document_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageDTO] = []

@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conv = Conversation(
        user_id=current_user.id,
        title=payload.title or "New Research Thread",
        document_id=payload.document_id
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@router.get("", response_model=List[ConversationResponse])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()).all()

@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation_history(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return conv

@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    db.delete(conv)
    db.commit()
    return {"success": True, "message": "Conversation deleted."}
