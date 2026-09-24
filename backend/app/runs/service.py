from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.errors import NotFoundError
from app.events.bus import EventBus
from app.projects.models import Project
from app.runs.models import Run
from app.runs.schemas import RunCreate


async def create_run(
    session: AsyncSession, bus: EventBus, project: Project, user: User, data: RunCreate
) -> Run:
    run = Run(
        project_id=project.id,
        created_by=user.id,
        objective=data.objective.strip(),
        strategy_key=data.strategy_key,
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
