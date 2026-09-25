from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.agents.models import AgentCapability
from app.tasks.models import TaskOrigin, TaskStatus


class PlannedTask(BaseModel):
    """Uma tarefa tal como o planner a propõe (validada antes de ir para a BD)."""

    key: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    acceptance_criteria: str = Field(default="", max_length=2000)
    required_capability: AgentCapability | None = None
    depends_on: list[str] = Field(default_factory=list, max_length=12)


class TaskOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    key: str
    title: str
    description: str
    acceptance_criteria: str
    required_capability: str | None
    status: TaskStatus
    assigned_agent_id: uuid.UUID | None
    assignment_reason: str | None
    priority: int
    result: str | None
    iteration_count: int
    max_iterations: int
    created_by: TaskOrigin
    depends_on: list[str]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    acceptance_criteria: str | None = Field(default=None, max_length=2000)
