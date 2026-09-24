from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.messages.models import MessageKind


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    task_id: uuid.UUID | None
    kind: MessageKind
    sender_agent_id: uuid.UUID | None
    sender_user_id: uuid.UUID | None
    recipient_agent_id: uuid.UUID | None
    content: str
    meta: dict
    created_at: datetime


class UserMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    recipient_agent_id: uuid.UUID | None = None


class AskAgentRequest(BaseModel):
    agent_id: uuid.UUID
    prompt: str | None = Field(default=None, max_length=8000)
