from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from sqlalchemy.orm import selectinload

from app.auth.dependencies import CurrentUser, SessionDep
from app.core.errors import NotFoundError
from app.runs import service as runs_service
from app.runs.dependencies import OwnedRun
from app.tasks import service
from app.tasks.models import Task
from app.tasks.schemas import TaskOut, TaskUpdate

router = APIRouter(tags=["tasks"])


@router.get("/runs/{run_id}/tasks", response_model=list[TaskOut])
async def list_tasks(run: OwnedRun, session: SessionDep) -> list[TaskOut]:
    return [service.to_out(t) for t in await service.list_tasks(session, run.id)]


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: uuid.UUID, data: TaskUpdate, user: CurrentUser, session: SessionDep, request: Request
) -> TaskOut:
    task = await session.get(Task, task_id, options=[selectinload(Task.dependencies)])
    if task is None:
        raise NotFoundError("Tarefa não encontrada")
    await runs_service.get_run(session, user, task.run_id)  # autorização
    task = await service.update_task(session, task, data)
    await request.app.state.bus.publish(
        task.run_id, "task.updated", service.to_out(task).model_dump(mode="json")
    )
    return service.to_out(task)
