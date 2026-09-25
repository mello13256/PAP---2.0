from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.workspace.models import ChangeKind


class FileEntry(BaseModel):
    path: str
    version: int
    size_bytes: int
    change_kind: ChangeKind
    author_agent_id: uuid.UUID | None
    author_user_id: uuid.UUID | None
    updated_at: datetime


class VersionOut(BaseModel):
    path: str
    version: int
    size_bytes: int
    change_kind: ChangeKind
    change_summary: str
    author_agent_id: uuid.UUID | None
    author_user_id: uuid.UUID | None
    run_id: uuid.UUID | None
    task_id: uuid.UUID | None
    created_at: datetime


class FileContent(VersionOut):
    content: str
    current_version: int


class FileWrite(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=200_000)
    base_version: int | None = Field(default=None, ge=0)
    summary: str = Field(default="", max_length=2000)


class DiffOut(BaseModel):
    path: str
    from_version: int
    to_version: int
    diff: str
