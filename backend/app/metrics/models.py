from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey
from app.db.types import enum_column, utcnow


class CallPurpose(StrEnum):
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    REVIEW = "REVIEW"
    REVISE = "REVISE"
    DECIDE = "DECIDE"
    FINALIZE = "FINALIZE"
    PING = "PING"


class LLMCall(UUIDPrimaryKey, Base):
    """Uma chamada (tentativa) a um LLM. Fonte de todas as métricas."""

    __tablename__ = "llm_calls"

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    purpose: Mapped[CallPurpose] = mapped_column(enum_column(CallPurpose))
    # None quando a API não fornece a contagem.
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    latency_ms: Mapped[int]
    success: Mapped[bool]
    error_type: Mapped[str | None] = mapped_column(String(40))
    # None quando o preço do modelo é desconhecido; 0 para modelos locais/gratuitos.
    estimated_cost_usd: Mapped[float | None]
    started_at: Mapped[datetime] = mapped_column(default=utcnow)


class RunMetrics(Base):
    """Métricas agregadas de um run, calculadas a partir de llm_calls, tasks, reviews..."""

    __tablename__ = "run_metrics"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True
    )
    execution_time_s: Mapped[float] = mapped_column(default=0.0)
    api_calls: Mapped[int] = mapped_column(default=0)
    failed_calls: Mapped[int] = mapped_column(default=0)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    tasks_total: Mapped[int] = mapped_column(default=0)
    tasks_completed: Mapped[int] = mapped_column(default=0)
    tasks_failed: Mapped[int] = mapped_column(default=0)
    reviews: Mapped[int] = mapped_column(default=0)
    revisions: Mapped[int] = mapped_column(default=0)
    decisions: Mapped[int] = mapped_column(default=0)
    human_interventions: Mapped[int] = mapped_column(default=0)
    estimated_cost_usd: Mapped[float | None]
    final_status: Mapped[str] = mapped_column(String(32))
    computed_at: Mapped[datetime] = mapped_column(default=utcnow)
