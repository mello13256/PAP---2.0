from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.db.types import enum_column, utcnow


class RunStatus(StrEnum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    AWAITING_PLAN_APPROVAL = "AWAITING_PLAN_APPROVAL"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_USER = "WAITING_USER"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Run(UUIDPrimaryKey, CreatedAt, Base):
    """Uma execução do MultiMind sobre um projeto."""

    __tablename__ = "runs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    objective: Mapped[str] = mapped_column(Text)
    strategy_key: Mapped[str] = mapped_column(String(60))
    # Snapshots: a configuração exata usada neste run (reprodutibilidade das experiências).
    strategy_config: Mapped[dict] = mapped_column(JSON, default=dict)
    limits: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[RunStatus] = mapped_column(enum_column(RunStatus), default=RunStatus.PENDING)
    final_result: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class RunEvent(Base):
    """Registo append-only de tudo o que acontece num run.

    Alimenta o streaming (SSE) e permite rever ("replay") execuções passadas.
    O ``id`` é sequencial e serve de cursor para retomar a ligação (Last-Event-ID).
    """

    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
