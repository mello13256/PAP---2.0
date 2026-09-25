from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.agents import service
from app.agents.factory import RuntimeFactory
from app.agents.models import Agent
from app.agents.schemas import (
    AgentCreate,
    AgentOut,
    AgentRemoved,
    AgentUpdate,
    PingRequest,
    PingResult,
    ProviderOut,
)
from app.auth.dependencies import CurrentUser, SessionDep
from app.providers.base import ProviderError
from app.providers.registry import ProviderRegistry

router = APIRouter(tags=["agents"])


def _registry(request: Request) -> ProviderRegistry:
    return request.app.state.providers


RegistryDep = Annotated[ProviderRegistry, Depends(_registry)]


def _out(agent: Agent, registry: ProviderRegistry) -> AgentOut:
    out = AgentOut.model_validate(agent)
    out.provider_available = agent.provider in registry
    return out


async def _owned_agent(agent_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Agent:
    return await service.get_agent(session, user, agent_id)


OwnedAgent = Annotated[Agent, Depends(_owned_agent)]


@router.get("/providers", response_model=list[ProviderOut])
async def list_providers(_: CurrentUser, registry: RegistryDep) -> list[ProviderOut]:
    return [ProviderOut(key=key) for key in registry.available()]


@router.get("/providers/{key}/models", response_model=list[str])
async def list_provider_models(key: str, _: CurrentUser, registry: RegistryDep) -> list[str]:
    """Modelos disponíveis num provider (ex.: modelos instalados no Ollama)."""
    try:
        return await registry.get(key).list_models() or []
    except ProviderError:
        return []


@router.get("/agents", response_model=list[AgentOut])
async def list_agents(
    user: CurrentUser, session: SessionDep, registry: RegistryDep
) -> list[AgentOut]:
    return [_out(a, registry) for a in await service.list_agents(session, user)]


@router.post("/agents/defaults", response_model=list[AgentOut], status_code=status.HTTP_201_CREATED)
async def create_default_agents(
    user: CurrentUser, session: SessionDep, registry: RegistryDep
) -> list[AgentOut]:
    """Cria os agentes pré-definidos (útil para contas criadas antes desta fase)."""
    return [_out(a, registry) for a in await service.create_default_agents(session, user)]


@router.post("/agents", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate, user: CurrentUser, session: SessionDep, registry: RegistryDep
) -> AgentOut:
    return _out(await service.create_agent(session, user, data, registry), registry)


@router.get("/agents/{agent_id}", response_model=AgentOut)
async def get_agent(agent: OwnedAgent, registry: RegistryDep) -> AgentOut:
    return _out(agent, registry)


@router.patch("/agents/{agent_id}", response_model=AgentOut)
async def update_agent(
    data: AgentUpdate, agent: OwnedAgent, session: SessionDep, registry: RegistryDep
) -> AgentOut:
    return _out(await service.update_agent(session, agent, data, registry), registry)


@router.delete("/agents/{agent_id}", response_model=AgentRemoved)
async def remove_agent(
    agent: OwnedAgent, session: SessionDep, registry: RegistryDep
) -> AgentRemoved:
    """Remove um agente.

    Se nunca participou em nada é apagado. Se já participou, é apenas desativado,
    para que o histórico (mensagens, versões, revisões) continue a saber quem foi.
    """
    if await service.remove_agent(session, agent):
        return AgentRemoved(deleted=True)
    return AgentRemoved(deleted=False, agent=_out(agent, registry))


@router.post("/agents/{agent_id}/ping", response_model=PingResult)
async def ping_agent(
    agent: OwnedAgent, request: Request, data: PingRequest | None = None
) -> PingResult:
    factory: RuntimeFactory = request.app.state.runtime_factory
    return await service.ping_agent(agent, factory, (data or PingRequest()).prompt)
