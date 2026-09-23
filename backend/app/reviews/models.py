from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.db.types import enum_column


class Verdict(StrEnum):
    APPROVED = "APPROVED"
    NEEDS_REVISION = "NEEDS_REVISION"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class HumanOverride(StrEnum):
    NONE = "NONE"
    FORCE_APPROVE = "FORCE_APPROVE"
    FORCE_REVISION = "FORCE_REVISION"


class Review(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("task_id", "round"),)

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    round: Mapped[int]
    reviewer_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL")
    )
    author_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL")
    )
    verdict: Mapped[Verdict] = mapped_column(enum_column(Verdict))
    summary: Mapped[str] = mapped_column(Text, default="")
    reviewed_versions: Mapped[list[str]] = mapped_column(JSON, default=list)
    human_override: Mapped[HumanOverride] = mapped_column(
        enum_column(HumanOverride), default=HumanOverride.NONE
    )
    human_comment: Mapped[str | None] = mapped_column(Text)


class ReviewIssue(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "review_issues"

    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), index=True
    )
    severity: Mapped[Severity] = mapped_column(enum_column(Severity))
    file_path: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str] = mapped_column(Text, default="")
    resolved: Mapped[bool] = mapped_column(default=False)
    resolved_in_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifact_versions.id", ondelete="SET NULL")
    )
