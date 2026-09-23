from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.db.types import enum_column


class ChangeKind(StrEnum):
    CREATE = "CREATE"
    MODIFY = "MODIFY"
    REVISION = "REVISION"  # alteração feita em resposta a uma revisão
    DELETE = "DELETE"


class Artifact(UUIDPrimaryKey, CreatedAt, Base):
    """Um ficheiro do workspace. O conteúdo vive nas versões."""

    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("project_id", "path"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(512))
    # Número da versão atual (0 = ainda sem versões). Ver DT-02.
    current_version: Mapped[int] = mapped_column(default=0)
    created_by_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    deleted_at: Mapped[datetime | None]


class ArtifactVersion(UUIDPrimaryKey, CreatedAt, Base):
    """Uma versão imutável de um ficheiro, ligada ao agente, tarefa e run que a criaram."""

    __tablename__ = "artifact_versions"
    __table_args__ = (UniqueConstraint("artifact_id", "version_number"),)

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int]
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifact_versions.id", ondelete="SET NULL")
    )
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))  # SHA-256
    size_bytes: Mapped[int]
    author_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), index=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    change_kind: Mapped[ChangeKind] = mapped_column(enum_column(ChangeKind))
    change_summary: Mapped[str] = mapped_column(Text, default="")
