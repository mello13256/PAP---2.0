from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.errors import NotFoundError
from app.db.types import utcnow
from app.projects.models import Project, ProjectStatus
from app.projects.schemas import ProjectCreate, ProjectUpdate


async def list_projects(
    session: AsyncSession, user: User, *, include_archived: bool = False
) -> list[Project]:
    query = select(Project).where(Project.owner_id == user.id)
    if not include_archived:
        query = query.where(Project.status == ProjectStatus.ACTIVE)
    result = await session.scalars(query.order_by(Project.updated_at.desc()))
    return list(result)


async def get_project(session: AsyncSession, user: User, project_id: uuid.UUID) -> Project:
    """Autorização por projeto: um projeto de outro utilizador é tratado como inexistente.

    Devolver 404 (e não 403) evita revelar que o projeto existe.
    """
    project = await session.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("Projeto não encontrado")
    return project


async def create_project(session: AsyncSession, user: User, data: ProjectCreate) -> Project:
    now = utcnow()
    project = Project(
        owner_id=user.id,
        name=data.name.strip(),
        description=data.description,
        created_at=now,
        updated_at=now,
    )
    session.add(project)
    await session.commit()
    return project


async def update_project(session: AsyncSession, project: Project, data: ProjectUpdate) -> Project:
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(project, field, value.strip() if field == "name" else value)
    await session.commit()
    await session.refresh(project)
    return project
