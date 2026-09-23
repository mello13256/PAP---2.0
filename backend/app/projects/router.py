from __future__ import annotations

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentUser, SessionDep
from app.projects import service
from app.projects.dependencies import OwnedProject
from app.projects.models import ProjectStatus
from app.projects.schemas import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    user: CurrentUser, session: SessionDep, include_archived: bool = False
) -> list[ProjectOut]:
    projects = await service.list_projects(session, user, include_archived=include_archived)
    return [ProjectOut.model_validate(p) for p in projects]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, user: CurrentUser, session: SessionDep) -> ProjectOut:
    return ProjectOut.model_validate(await service.create_project(session, user, data))


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project: OwnedProject) -> ProjectOut:
    return ProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    data: ProjectUpdate, project: OwnedProject, session: SessionDep
) -> ProjectOut:
    return ProjectOut.model_validate(await service.update_project(session, project, data))


@router.delete("/{project_id}", response_model=ProjectOut)
async def archive_project(project: OwnedProject, session: SessionDep) -> ProjectOut:
    """Arquiva (não apaga): o histórico de runs, versões e decisões é preservado."""
    updated = await service.update_project(
        session, project, ProjectUpdate(status=ProjectStatus.ARCHIVED)
    )
    return ProjectOut.model_validate(updated)
