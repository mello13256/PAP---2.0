from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.runs.models import RunStatus


class RunCreate(BaseModel):
    objective: str = Field(min_length=1, max_length=4000)
    strategy_key: str = Field(default="collaborative", min_length=1, max_length=60)
    # Agentes participantes, por ordem (o 1.º tem papel especial em algumas estratégias).
    # Vazio = todos os agentes ativos do utilizador.
    agent_ids: list[uuid.UUID] = Field(default_factory=list, max_length=6)
    autostart: bool = True


class StrategyOut(BaseModel):
    key: str
    name: str
    description: str
    min_agents: int


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    objective: str
    strategy_key: str
    strategy_config: dict
    status: RunStatus
    final_result: str | None
    failure_reason: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
