from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey


class AgentCapability(StrEnum):
    PLANNING = "planning"
    ARCHITECTURE = "architecture"
    CODING = "coding"
    REVIEW = "review"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    SYNTHESIS = "synthesis"


class Agent(UUIDPrimaryKey, CreatedAt, Base):
    """Configuração de um agente: *quem* é (persona, modelo, capacidades).

    Não sabe falar com APIs; isso é responsabilidade do provider (ver ``providers/``).
    """

    __tablename__ = "agents"

    # None = agente de sistema, disponível para todos os utilizadores.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    # Parâmetros pequenos e validados (temperature, max_output_tokens, ...).
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)
