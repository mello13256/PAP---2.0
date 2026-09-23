from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.db.types import enum_column


class DecisionStatus(StrEnum):
    OPEN = "OPEN"
    AWAITING_USER = "AWAITING_USER"
    DECIDED = "DECIDED"


class DecidedBy(StrEnum):
    ARBITER_AGENT = "ARBITER_AGENT"
    CONSENSUS = "CONSENSUS"
    USER = "USER"
    ORCHESTRATOR = "ORCHESTRATOR"


class Decision(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "decisions"
    __table_args__ = (UniqueConstraint("run_id", "number"),)

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    number: Mapped[int]  # "DECISION #12"
    question: Mapped[str] = mapped_column(Text)
    discussion_summary: Mapped[str] = mapped_column(Text, default="")
    justification: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[DecidedBy | None] = mapped_column(enum_column(DecidedBy))
    status: Mapped[DecisionStatus] = mapped_column(
        enum_column(DecisionStatus), default=DecisionStatus.OPEN
    )
    decided_at: Mapped[datetime | None]


class DecisionProposal(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "decision_proposals"

    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"))
    label: Mapped[str] = mapped_column(String(8))  # "A", "B", ...
    content: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text, default="")
    is_chosen: Mapped[bool] = mapped_column(default=False)  # ver DT-02
