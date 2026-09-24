from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.runs.models import RunStatus


class RunCreate(BaseModel):
    objective: str = Field(min_length=1, max_length=4000)
    strategy_key: str = Field(default="collaborative", min_length=1, max_length=60)


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    objective: str
    strategy_key: str
    status: RunStatus
    final_result: str | None
    failure_reason: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
