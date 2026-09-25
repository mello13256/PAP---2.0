"""Contexto partilhado por todos os componentes durante um run."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.models import Agent
from app.agents.runtime import AgentRuntime
from app.events.bus import EventBus
from app.messages import service as messages
from app.messages.models import Message, MessageKind
from app.metrics.models import LLMCall
from app.orchestration.strategies import Strategy


class LimitExceeded(Exception):
    """Um limite do run foi atingido (prevenção de loops e de custos)."""


@dataclass
class RunControl:
    """Pausa cooperativa: o orquestrador só pára entre passos (a chamada em curso termina)."""

    _running: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        self._running.set()

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    @property
    def paused(self) -> bool:
        return not self._running.is_set()

    async def wait_if_paused(self) -> None:
        await self._running.wait()


@dataclass
class RunContext:
    run_id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID | None
    objective: str
    strategy: Strategy
    participants: list[Agent]  # por ordem: o 1.º tem papel especial em algumas estratégias
    runtimes: dict[uuid.UUID, AgentRuntime]
    sessionmaker: async_sessionmaker[AsyncSession]
    bus: EventBus
    workspaces_dir: Path | None
    control: RunControl = field(default_factory=RunControl)
    started: float = field(default_factory=time.monotonic)

    @property
    def names(self) -> dict[uuid.UUID, str]:
        return {a.id: a.name for a in self.participants}

    def agent(self, agent_id: uuid.UUID) -> Agent:
        return next(a for a in self.participants if a.id == agent_id)

    async def say(self, kind: MessageKind, content: str, **kwargs) -> Message:
        async with self.sessionmaker() as session:
            return await messages.post_message(
                session, self.bus, run_id=self.run_id, kind=kind, content=content, **kwargs
            )

    async def event(self, type: str, payload: dict | None = None, *, persist: bool = True) -> None:
        await self.bus.publish(self.run_id, type, payload, persist=persist)

    async def llm_calls(self) -> int:
        async with self.sessionmaker() as session:
            return (
                await session.scalar(
                    select(func.count()).select_from(LLMCall).where(LLMCall.run_id == self.run_id)
                )
                or 0
            )

    async def checkpoint(self) -> None:
        """Chamado antes de cada passo: pausa, limites de chamadas e de tempo."""
        await self.control.wait_if_paused()
        limits = self.strategy.limits
        minutes = (time.monotonic() - self.started) / 60
        if minutes > limits.max_minutes:
            raise LimitExceeded(f"Tempo máximo do run atingido ({limits.max_minutes} min)")
        calls = await self.llm_calls()
        if calls >= limits.max_llm_calls:
            raise LimitExceeded(f"Número máximo de chamadas a LLMs atingido ({calls})")
