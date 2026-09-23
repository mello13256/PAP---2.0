from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey


class User(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    # Apenas o hash (argon2). A password nunca é guardada.
    password_hash: Mapped[str] = mapped_column(String(255))
