from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.db.types import enum_column


class MessageKind(StrEnum):
    USER = "USER"  # escrita pelo utilizador
    ORCHESTRATOR = "ORCHESTRATOR"  # o orquestrador a comunicar (atribuições, instruções)
    AGENT = "AGENT"  # um agente a falar (com outro agente ou com todos)
    TASK_RESULT = "TASK_RESULT"  # resultado entregue de uma tarefa
    REVIEW = "REVIEW"  # revisão estruturada
    DECISION = "DECISION"  # decisão registada
    SYSTEM = "SYSTEM"  # eventos do sistema (limites, erros, pausas)


class Message(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "messages"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[MessageKind] = mapped_column(enum_column(MessageKind))
    sender_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL")
    )
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # None = difusão (todos os agentes do run).
    recipient_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL")
    )
    content: Mapped[str] = mapped_column(Text)
    # "metadata" é um nome reservado nos modelos SQLAlchemy; o atributo chama-se "meta".
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
