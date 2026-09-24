from __future__ import annotations

import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.defaults import DEFAULT_AGENTS
from app.agents.factory import RuntimeFactory
from app.agents.models import Agent
from app.agents.runtime import CallContext
from app.agents.schemas import AgentCreate, AgentUpdate, PingResult
from app.auth.models import User
from app.core.errors import NotFoundError
from app.metrics.models import CallPurpose
from app.providers.base import ChatMessage, ProviderError
from app.providers.registry import ProviderRegistry, UnknownProviderError


async def create_default_agents(session: AsyncSession, user: User) -> list[Agent]:
    agents = [
        Agent(owner_id=user.id, **{**spec, "capabilities": [str(c) for c in spec["capabilities"]]})
        for spec in DEFAULT_AGENTS
    ]
    session.add_all(agents)
    await session.commit()
    return agents


async def list_agents(session: AsyncSession, user: User) -> list[Agent]:
    result = await session.scalars(
        select(Agent).where(Agent.owner_id == user.id).order_by(Agent.created_at, Agent.name)
    )
    return list(result)


async def get_agent(session: AsyncSession, user: User, agent_id: uuid.UUID) -> Agent:
    agent = await session.get(Agent, agent_id)
    if agent is None or agent.owner_id != user.id:
        raise NotFoundError("Agente não encontrado")
    return agent


def _check_provider(registry: ProviderRegistry, key: str) -> None:
    if key not in registry:
        raise UnknownProviderError(
            f"Provider '{key}' não está configurado neste servidor. "
            f"Disponíveis: {', '.join(registry.available())}"
        )


async def create_agent(
    session: AsyncSession, user: User, data: AgentCreate, registry: ProviderRegistry
) -> Agent:
    _check_provider(registry, data.provider)
    agent = Agent(
        owner_id=user.id,
        name=data.name.strip(),
        provider=data.provider,
        model=data.model.strip(),
        capabilities=[str(c) for c in data.capabilities],
        system_prompt=data.system_prompt,
        config=data.config.model_dump(exclude_none=True),
        enabled=data.enabled,
    )
    session.add(agent)
    await session.commit()
    return agent


async def update_agent(
    session: AsyncSession, agent: Agent, data: AgentUpdate, registry: ProviderRegistry
) -> Agent:
    changes = data.model_dump(exclude_unset=True)
    if changes.get("provider") is not None:
        _check_provider(registry, changes["provider"])
    for field, value in changes.items():
        if value is None:
            continue
        if field == "capabilities":
            value = [str(c) for c in value]
        elif field == "config":
            value = data.config.model_dump(exclude_none=True)
        elif field in ("name", "model"):
            value = value.strip()
        setattr(agent, field, value)
    await session.commit()
    await session.refresh(agent)
    return agent


async def ping_agent(agent: Agent, factory: RuntimeFactory, prompt: str) -> PingResult:
    """Chamada real ao modelo do agente (fica registada nas métricas como PING)."""
    t0 = time.perf_counter()
    try:
        runtime = factory.build(agent)
        result = await runtime.generate(
            [ChatMessage.user(prompt)], context=CallContext(CallPurpose.PING)
        )
    except (ProviderError, UnknownProviderError) as exc:
        return PingResult(
            ok=False,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            error_kind=str(getattr(exc, "kind", "unknown_provider")),
            error=str(exc),
        )
    return PingResult(
        ok=True,
        text=result.text,
        model=result.model,
        latency_ms=int((time.perf_counter() - t0) * 1000),
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
    )
