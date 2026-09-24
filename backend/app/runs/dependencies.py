from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends

from app.auth.dependencies import CurrentUser, SessionDep
from app.runs import service
from app.runs.models import Run


async def get_owned_run(run_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Run:
    return await service.get_run(session, user, run_id)


OwnedRun = Annotated[Run, Depends(get_owned_run)]
