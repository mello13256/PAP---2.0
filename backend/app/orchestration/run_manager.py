"""Gestão das execuções em curso: iniciar, pausar, retomar, cancelar."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.factory import RuntimeFactory
from app.agents.models import Agent
from app.core.background import BackgroundTasks
from app.core.errors import InvalidStateError
from app.db.types import utcnow
from app.events.bus import EventBus
from app.orchestration.context import RunContext, RunControl
from app.orchestration.orchestrator import execute_run, set_run_status
from app.orchestration.strategies import STRATEGIES
from app.projects.models import Project
from app.runs.models import Run, RunStatus

logger = logging.getLogger(__name__)

ACTIVE = {RunStatus.PLANNING, RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.FINALIZING}


@dataclass
class RunHandle:
    task: asyncio.Task
    ctx: RunContext


class RunManager:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        bus: EventBus,
        factory: RuntimeFactory,
        background: BackgroundTasks,
        workspaces_dir,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._bus = bus
        self.factory = factory  # substituível (ex.: nos testes)
        self._background = background
        self._workspaces_dir = workspaces_dir
        self._handles: dict[uuid.UUID, RunHandle] = {}

    async def build_context(self, run_id: uuid.UUID) -> RunContext:
        async with self._sessionmaker() as session:
            run = await session.get(Run, run_id)
            project = await session.get(Project, run.project_id)
            agent_ids = [uuid.UUID(a) for a in run.strategy_config.get("agent_ids", [])]
            agents = list(await session.scalars(select(Agent).where(Agent.id.in_(agent_ids))))
        order = {a: i for i, a in enumerate(agent_ids)}
        agents.sort(key=lambda a: order[a.id])
        strategy = STRATEGIES[run.strategy_key]
        return RunContext(
            run_id=run.id,
            project_id=project.id,
            user_id=run.created_by,
            objective=run.objective,
            strategy=strategy,
            participants=agents,
            runtimes={a.id: self.factory.build(a) for a in agents},
            sessionmaker=self._sessionmaker,
            bus=self._bus,
            workspaces_dir=self._workspaces_dir,
            control=RunControl(),
        )

    async def start(self, run_id: uuid.UUID) -> None:
        async with self._sessionmaker() as session:
            run = await session.get(Run, run_id)
            if run.status is not RunStatus.PENDING:
                raise InvalidStateError(
                    f"Só é possível iniciar runs pendentes (estado: {run.status})"
                )
        ctx = await self.build_context(run_id)

        async def _run() -> None:
            try:
                await execute_run(ctx)
            finally:
                self._handles.pop(run_id, None)

        task = self._background.spawn(_run(), name=f"run:{run_id}")
        self._handles[run_id] = RunHandle(task, ctx)

    def _handle(self, run_id: uuid.UUID) -> RunHandle:
        handle = self._handles.get(run_id)
        if handle is None:
            raise InvalidStateError("Este run não está em execução")
        return handle

    async def pause(self, run_id: uuid.UUID) -> None:
        handle = self._handle(run_id)
        handle.ctx.control.pause()
        await set_run_status(handle.ctx, RunStatus.PAUSED)

    async def resume(self, run_id: uuid.UUID) -> None:
        handle = self._handle(run_id)
        handle.ctx.control.resume()
        await set_run_status(handle.ctx, RunStatus.RUNNING)

    async def cancel(self, run_id: uuid.UUID) -> None:
        handle = self._handle(run_id)
        handle.ctx.control.resume()  # para que a tarefa possa terminar
        handle.task.cancel()
        await asyncio.gather(handle.task, return_exceptions=True)

    def is_active(self, run_id: uuid.UUID) -> bool:
        return run_id in self._handles

    async def recover_interrupted(self) -> None:
        """No arranque: runs que estavam a correr quando o servidor parou ficam FAILED."""
        async with self._sessionmaker() as session:
            runs = list(await session.scalars(select(Run).where(Run.status.in_(ACTIVE))))
            for run in runs:
                run.status = RunStatus.FAILED
                run.failure_reason = "Interrompido: o servidor foi reiniciado durante a execução"
                run.finished_at = utcnow()
            await session.commit()
        if runs:
            logger.warning("%d run(s) interrompido(s) marcados como FAILED", len(runs))
