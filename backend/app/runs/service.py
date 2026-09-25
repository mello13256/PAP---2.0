from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import service as agents_service
from app.auth.models import User
from app.core.errors import AppError, NotFoundError
from app.events.bus import EventBus
from app.orchestration.strategies import STRATEGIES
from app.projects.models import Project
from app.runs.models import Run
from app.runs.schemas import RunCreate


class ValidationError(AppError):
    status_code = 422
    code = "invalid_run"


async def create_run(
    session: AsyncSession, bus: EventBus, project: Project, user: User, data: RunCreate
) -> Run:
    strategy = STRATEGIES.get(data.strategy_key)
    if strategy is None:
        raise ValidationError(
            f"Estratégia desconhecida: {data.strategy_key}. Disponíveis: {', '.join(STRATEGIES)}"
        )
    own = {a.id: a for a in await agents_service.list_agents(session, user)}
    if data.agent_ids:
        missing = [a for a in data.agent_ids if a not in own]
        if missing:
            raise NotFoundError("Agente não encontrado")
        agents = [own[a] for a in dict.fromkeys(data.agent_ids)]
    else:
        agents = [a for a in own.values() if a.enabled and a.provider != "fake"]
    agents = [a for a in agents if a.enabled]
    if len(agents) < strategy.min_agents:
        raise ValidationError(
            f"A estratégia '{strategy.name}' precisa de pelo menos {strategy.min_agents} "
            f"agente(s) ativo(s); foram indicados {len(agents)}."
        )
    run = Run(
        project_id=project.id,
        created_by=user.id,
        objective=data.objective.strip(),
        strategy_key=strategy.key,
        strategy_config={**strategy.snapshot(), "agent_ids": [str(a.id) for a in agents]},
        limits=strategy.snapshot()["limits"],
    )
    session.add(run)
    await session.commit()
    await bus.publish(run.id, "run.created", {"run_id": run.id, "objective": run.objective})
    return run


async def list_runs(session: AsyncSession, project: Project) -> list[Run]:
    result = await session.scalars(
        select(Run).where(Run.project_id == project.id).order_by(Run.created_at.desc())
    )
    return list(result)


async def get_run(session: AsyncSession, user: User, run_id: uuid.UUID) -> Run:
    """Autorização: um run pertence a um projeto, que pertence a um utilizador."""
    row = (
        await session.execute(
            select(Run, Project.owner_id)
            .join(Project, Project.id == Run.project_id)
            .where(Run.id == run_id)
        )
    ).first()
    if row is None or row.owner_id != user.id:
        raise NotFoundError("Execução não encontrada")
    return row.Run


async def recent_runs(session: AsyncSession, user: User, limit: int = 10) -> list[tuple[Run, str]]:
    rows = await session.execute(
        select(Run, Project.name)
        .join(Project, Project.id == Run.project_id)
        .where(Project.owner_id == user.id)
        .order_by(Run.created_at.desc())
        .limit(limit)
    )
    return [(run, name) for run, name in rows.all()]
