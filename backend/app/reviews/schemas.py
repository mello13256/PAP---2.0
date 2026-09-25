from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.reviews.models import HumanOverride, Severity, Verdict


class ReviewIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    severity: Severity
    file_path: str | None
    description: str
    suggestion: str
    resolved: bool


class ReviewOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    task_key: str
    round: int
    reviewer_agent_id: uuid.UUID | None
    author_agent_id: uuid.UUID | None
    verdict: Verdict
    summary: str
    reviewed_versions: list[str]
    human_override: HumanOverride
    human_comment: str | None
    issues: list[ReviewIssueOut]
    created_at: datetime
