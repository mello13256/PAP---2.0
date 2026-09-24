"""Mensagens de um run: guardadas na BD e publicadas em tempo real."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.bus import EventBus
from app.messages.models import Message, MessageKind
from app.messages.schemas import MessageOut


async def post_message(
    session: AsyncSession,
    bus: EventBus,
    *,
    run_id: uuid.UUID,
    kind: MessageKind,
    content: str,
    task_id: uuid.UUID | None = None,
    sender_agent_id: uuid.UUID | None = None,
    sender_user_id: uuid.UUID | None = None,
    recipient_agent_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> Message:
    message = Message(
        run_id=run_id,
        task_id=task_id,
        kind=kind,
        content=content,
        sender_agent_id=sender_agent_id,
        sender_user_id=sender_user_id,
        recipient_agent_id=recipient_agent_id,
        meta=meta or {},
    )
    session.add(message)
    await session.commit()
    await bus.publish(
        run_id, "message.created", MessageOut.model_validate(message).model_dump(mode="json")
    )
    return message


async def list_messages(
    session: AsyncSession, run_id: uuid.UUID, *, limit: int | None = None
) -> list[Message]:
    """Mensagens por ordem cronológica (as ``limit`` mais recentes, se indicado)."""
    query = select(Message).where(Message.run_id == run_id)
    if limit is None:
        return list(await session.scalars(query.order_by(Message.created_at)))
    recent = await session.scalars(query.order_by(Message.created_at.desc()).limit(limit))
    return list(reversed(list(recent)))
