from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.db.types import enum_column


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"  # à espera do utilizador
    REVIEW = "REVIEW"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskOrigin(StrEnum):
    PLANNER = "PLANNER"
    USER = "USER"


# Relação N:N da tabela tasks consigo própria: "task_id depende de depends_on_id".
task_dependencies = Table(
    "task_dependencies",
    Base.metadata,
    Column("task_id", Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("depends_on_id", Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    CheckConstraint("task_id <> depends_on_id", name="no_self_dependency"),
)


class Task(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("run_id", "key"),)

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(20))  # id curto dado pelo planner: "T3"
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    acceptance_criteria: Mapped[str] = mapped_column(Text, default="")
    required_capability: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[TaskStatus] = mapped_column(enum_column(TaskStatus), default=TaskStatus.PENDING)
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), index=True
    )
    assignment_reason: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(default=0)
    result: Mapped[str | None] = mapped_column(Text)
    iteration_count: Mapped[int] = mapped_column(default=0)
    max_iterations: Mapped[int] = mapped_column(default=3)
    created_by: Mapped[TaskOrigin] = mapped_column(
        enum_column(TaskOrigin), default=TaskOrigin.PLANNER
    )
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]

    # lazy="raise": obriga a carregar as dependências explicitamente (evita
    # consultas escondidas, que em código assíncrono dão erro).
    dependencies: Mapped[list[Task]] = relationship(
        secondary=task_dependencies,
        primaryjoin=lambda: Task.id == task_dependencies.c.task_id,
        secondaryjoin=lambda: Task.id == task_dependencies.c.depends_on_id,
        lazy="raise",
    )
