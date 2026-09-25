from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.agents.models import AgentCapability


class AgentConfig(BaseModel):
    """Parâmetros de geração. Validados para não chegarem valores absurdos à API."""

    model_config = ConfigDict(extra="forbid")

    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int = Field(default=4096, ge=256, le=65536)


_NAME = Field(min_length=1, max_length=80)
_PROVIDER = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9_]+$")
_MODEL = Field(min_length=1, max_length=120)


class AgentCreate(BaseModel):
    name: str = _NAME
    provider: str = _PROVIDER
    model: str = _MODEL
    capabilities: list[AgentCapability] = Field(default_factory=list, max_length=10)
    system_prompt: str = Field(default="", max_length=8000)
    config: AgentConfig = Field(default_factory=AgentConfig)
    enabled: bool = True


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    provider: str | None = Field(default=None, min_length=1, max_length=40, pattern=r"^[a-z0-9_]+$")
    model: str | None = Field(default=None, min_length=1, max_length=120)
    capabilities: list[AgentCapability] | None = Field(default=None, max_length=10)
    system_prompt: str | None = Field(default=None, max_length=8000)
    config: AgentConfig | None = None
    enabled: bool | None = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    provider: str
    model: str
    capabilities: list[str]
    system_prompt: str
    config: dict
    enabled: bool
    provider_available: bool = False  # o provider está configurado neste servidor?
    created_at: datetime


class PingRequest(BaseModel):
    prompt: str = Field(
        default="Apresenta-te numa frase, em português.", min_length=1, max_length=2000
    )


class PingResult(BaseModel):
    ok: bool
    text: str = ""
    model: str | None = None
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_kind: str | None = None
    error: str | None = None


class ProviderOut(BaseModel):
    key: str
    supports_listing_models: bool = True


class AgentRemoved(BaseModel):
    deleted: bool  # True = apagado; False = já tinha sido usado, por isso foi só desativado
    agent: AgentOut | None = None
