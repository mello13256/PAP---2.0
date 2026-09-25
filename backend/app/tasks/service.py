from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import InvalidStateError, NotFoundError
from app.db.types import utcnow
from app.tasks.graph import InvalidPlanError, topological_order
from app.tasks.models import Task, TaskStatus
from app.tasks.schemas import PlannedTask, TaskOut, TaskUpdate
from app.tasks.state import FINISHED, check_transition

MAX_TASKS = 10


def validate_plan(planned: Sequence[PlannedTask], *, max_tasks: int = MAX_TASKS) -> list[str]:
    if not planned:
        raise InvalidPlanError("O plano não tem tarefas")
    if len(planned) > max_tasks:
        raise InvalidPlanError(f"O plano tem {len(planned)} tarefas; o máximo é {max_tasks}")
    keys = [t.key for t in planned]
    if len(set(keys)) != len(keys):
        raise InvalidPlanError("Há tarefas com a mesma chave")
    return topological_order({t.key: t.depends_on for t in planned})


async def create_tasks(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    project_id: uuid.UUID,
    planned: Sequence[PlannedTask],
    max_iterations: int,
) -> list[Task]:
    order = validate_plan(planned)
    by_key = {t.key: t for t in planned}
    tasks: dict[str, Task] = {}
    for priority, key in enumerate(order):
        spec = by_key[key]
        task = Task(
            run_id=run_id,
            project_id=project_id,
            key=key,
            title=spec.title,
            description=spec.description,
            acceptance_criteria=spec.acceptance_criteria,
            required_capability=spec.required_capability.value
            if spec.required_capability
            else None,
            priority=priority,
            max_iterations=max_iterations,
        )
        task.dependencies = [tasks[dep] for dep in spec.depends_on]
        tasks[key] = task
        session.add(task)
    await session.commit()
    return [tasks[k] for k in order]


async def list_tasks(session: AsyncSession, run_id: uuid.UUID) -> list[Task]:
    result = await session.scalars(
        select(Task)
        .where(Task.run_id == run_id)
        .options(selectinload(Task.dependencies))
        .order_by(Task.priority)
    )
    return list(result)


def ready_tasks(tasks: Sequence[Task]) -> list[Task]:
    """Tarefas PENDING cujas dependências estão todas COMPLETED."""
    return [
        t
        for t in tasks
        if t.status is TaskStatus.PENDING
        and all(d.status is TaskStatus.COMPLETED for d in t.dependencies)
    ]


def blocked_tasks(tasks: Sequence[Task]) -> list[Task]:
    """Tarefas que nunca poderão começar porque uma dependência falhou/foi cancelada."""
    bad = {TaskStatus.FAILED, TaskStatus.CANCELLED}
    return [
        t
        for t in tasks
        if t.status is TaskStatus.PENDING and any(d.status in bad for d in t.dependencies)
    ]


async def set_status(
    session: AsyncSession, task_id: uuid.UUID, status: TaskStatus, **fields
) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise NotFoundError("Tarefa não encontrada")
    check_transition(task.status, status)
    task.status = status
    if status is TaskStatus.RUNNING and task.started_at is None:
        task.started_at = utcnow()
    if status in FINISHED:
        task.completed_at = utcnow()
    for key, value in fields.items():
        setattr(task, key, value)
    await session.commit()
    return task


async def update_task(session: AsyncSession, task: Task, data: TaskUpdate) -> Task:
    """Edição pelo utilizador: só antes de a tarefa começar (ou quando está à espera dele)."""
    if task.status not in (TaskStatus.PENDING, TaskStatus.WAITING):
        raise InvalidStateError("Só é possível editar tarefas pendentes ou em espera")
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(task, field, value)
    await session.commit()
    return task


def to_out(task: Task) -> TaskOut:
    return TaskOut(
        id=task.id,
        run_id=task.run_id,
        key=task.key,
        title=task.title,
        description=task.description,
        acceptance_criteria=task.acceptance_criteria,
        required_capability=task.required_capability,
        status=task.status,
        assigned_agent_id=task.assigned_agent_id,
        assignment_reason=task.assignment_reason,
        priority=task.priority,
        result=task.result,
        iteration_count=task.iteration_count,
        max_iterations=task.max_iterations,
        created_by=task.created_by,
        depends_on=[d.key for d in task.dependencies],
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )
