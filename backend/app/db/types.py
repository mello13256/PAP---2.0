"""Tipos de coluna partilhados, portáveis entre SQLite e PostgreSQL."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Data/hora sempre em UTC e sempre com fuso horário.

    O SQLite não guarda fusos horários; este tipo garante que o que sai da BD é
    igual ao que entrou (um ``datetime`` "aware" em UTC), em qualquer motor.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Datas sem fuso horário não são permitidas; usa utcnow().")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_cls: type[enum.Enum]) -> Enum:
    """Enum guardado como texto, com CHECK constraint (funciona em qualquer BD)."""
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [member.value for member in e],
        name=f"ck_{enum_cls.__name__.lower()}",
        validate_strings=True,
    )
