from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey


class Experiment(UUIDPrimaryKey, CreatedAt, Base):
    """O mesmo objetivo corrido com várias estratégias, N vezes cada.

    Os runs da experiência apontam para ela (``runs.experiment_id``).
    """

    __tablename__ = "experiments"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    objective: Mapped[str] = mapped_column(Text)
    strategies: Mapped[list[str]] = mapped_column(JSON, default=list)
    repetitions: Mapped[int] = mapped_column(default=1)
