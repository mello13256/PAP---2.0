from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.db.types import enum_column


class InterventionKind(StrEnum):
    APPROVE_PLAN = "APPROVE_PLAN"
    CHOOSE_OPTION = "CHOOSE_OPTION"
    REVIEW_ESCALATION = "REVIEW_ESCALATION"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"


class InterventionStatus(StrEnum):
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    EXPIRED = "EXPIRED"


class Intervention(UUIDPrimaryKey, CreatedAt, Base):
    """Um pedido do sistema ao utilizador (human-in-the-loop)."""

    __tablename__ = "interventions"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("decisions.id", ondelete="SET NULL")
    )
    kind: Mapped[InterventionKind] = mapped_column(enum_column(InterventionKind))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[InterventionStatus] = mapped_column(
        enum_column(InterventionStatus), default=InterventionStatus.PENDING
    )
    response: Mapped[dict | None] = mapped_column(JSON)
    responded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    answered_at: Mapped[datetime | None]
