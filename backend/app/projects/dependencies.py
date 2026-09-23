from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends

from app.auth.dependencies import CurrentUser, SessionDep
from app.projects import service
from app.projects.models import Project


async def get_owned_project(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Project:
    """Dependência usada por TODOS os endpoints que operam sobre um projeto."""
    return await service.get_project(session, user, project_id)


OwnedProject = Annotated[Project, Depends(get_owned_project)]
