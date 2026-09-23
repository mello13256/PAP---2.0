"""Base declarativa de todos os modelos SQLAlchemy."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import MetaData, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import UTCDateTime, utcnow

# Nomes previsíveis para constraints: necessário para o Alembic conseguir
# alterá-las mais tarde (sobretudo em SQLite, onde as migrações recriam tabelas).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: UTCDateTime(), uuid.UUID: Uuid()}


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class CreatedAt:
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
