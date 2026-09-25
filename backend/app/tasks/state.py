"""Máquina de estados das tarefas: transições permitidas, validadas num só sítio."""

from __future__ import annotations

from app.core.errors import InvalidStateError
from app.tasks.models import TaskStatus as S

ALLOWED: dict[S, set[S]] = {
    S.PENDING: {S.RUNNING, S.WAITING, S.CANCELLED},
    S.RUNNING: {S.REVIEW, S.COMPLETED, S.FAILED, S.WAITING, S.CANCELLED},
    S.REVIEW: {S.RUNNING, S.COMPLETED, S.FAILED, S.WAITING, S.CANCELLED},
    S.WAITING: {S.PENDING, S.RUNNING, S.CANCELLED},
    S.FAILED: set(),
    S.COMPLETED: set(),
    S.CANCELLED: set(),
}

FINISHED = {S.COMPLETED, S.FAILED, S.CANCELLED}


def check_transition(current: S, new: S) -> None:
    if new is current:
        return
    if new not in ALLOWED[current]:
        raise InvalidStateError(f"Transição inválida da tarefa: {current} → {new}")
