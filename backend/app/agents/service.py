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
    """Cria os agentes pré-definidos que o utilizador ainda não tem (pelo nome).

    Pode ser chamado várias vezes sem criar duplicados.
    """
    existing = {a.name for a in await list_agents(session, user)}
    agents = [
        Agent(owner_id=user.id, **{**spec, "capabilities": [str(c) for c in spec["capabilities"]]})
        for spec in DEFAULT_AGENTS
        if spec["name"] not in existing
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


async def is_agent_used(session: AsyncSession, agent_id: uuid.UUID) -> bool:
    """O agente aparece em algum histórico (tarefas, mensagens, versões, revisões, chamadas)?"""
    from app.messages.models import Message
    from app.metrics.models import LLMCall
    from app.reviews.models import Review
    from app.tasks.models import Task
    from app.workspace.models import ArtifactVersion

    checks = [
        select(Task.id).where(Task.assigned_agent_id == agent_id),
        select(Message.id).where(
            (Message.sender_agent_id == agent_id) | (Message.recipient_agent_id == agent_id)
        ),
        select(ArtifactVersion.id).where(ArtifactVersion.author_agent_id == agent_id),
        select(Review.id).where(
            (Review.reviewer_agent_id == agent_id) | (Review.author_agent_id == agent_id)
        ),
        select(LLMCall.id).where(LLMCall.agent_id == agent_id),
    ]
    for query in checks:
        if await session.scalar(query.limit(1)) is not None:
            return True
    return False


async def remove_agent(session: AsyncSession, agent: Agent) -> bool:
    """Apaga o agente se nunca foi usado; caso contrário desativa-o. Devolve True se apagou."""
    if await is_agent_used(session, agent.id):
        agent.enabled = False
        await session.commit()
        return False
    await session.delete(agent)
    await session.commit()
    return True


async def remove_duplicate_agents(session: AsyncSession) -> int:
    """Arrumação no arranque: agentes repetidos (mesmo dono, nome, fornecedor e modelo).

    Fica o mais antigo. Os repetidos nunca usados são apagados; os que já têm
    histórico ficam desativados (para não participarem duas vezes num run).
    Devolve quantos foram tratados.
    """
    agents = list(await session.scalars(select(Agent).order_by(Agent.created_at, Agent.id)))
    seen: set[tuple] = set()
    handled = 0
    for agent in agents:
        key = (agent.owner_id, agent.name.strip().lower(), agent.provider, agent.model)
        if key not in seen:
            seen.add(key)
            continue
        if await is_agent_used(session, agent.id):
            if agent.enabled:
                agent.enabled = False
                handled += 1
        else:
            await session.delete(agent)
            handled += 1
    await session.commit()
    return handled
