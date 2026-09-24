import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Conversation, User
from app.models.enums import MessageRole

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    updated_at: datetime


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    content: str
    payload: dict[str, Any] | None
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageRead]


def get_conversation(
    conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    company_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Conversation).where(Conversation.user_id == user.id)
    if company_id is not None:
        query = query.where(Conversation.company_id == company_id)
    return db.scalars(query.order_by(Conversation.updated_at.desc()).limit(limit)).all()


@router.get("/{conversation_id}", response_model=ConversationDetail)
def read_conversation(conversation: Conversation = Depends(get_conversation)):
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation: Conversation = Depends(get_conversation), db: Session = Depends(get_db)):
    db.delete(conversation)
    db.commit()
