"""Validação do grafo de tarefas produzido pelo planner.

Um plano é aceite apenas se for um DAG (grafo dirigido acíclico): se a tarefa A
depende de B e B depende de A, nenhuma pode começar e o run ficaria preso.
Usamos o algoritmo de Kahn: remove repetidamente tarefas sem dependências por
satisfazer; se no fim sobrarem tarefas, existe um ciclo.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence

from app.core.errors import AppError


class InvalidPlanError(AppError):
    status_code = 422
    code = "invalid_plan"


def topological_order(dependencies: Mapping[str, Sequence[str]]) -> list[str]:
    """Ordem de execução possível.

    Lança InvalidPlanError se houver ciclos ou referências inválidas.
    """
    for key, deps in dependencies.items():
        for dep in deps:
            if dep not in dependencies:
                raise InvalidPlanError(f"A tarefa {key} depende de {dep}, que não existe")
            if dep == key:
                raise InvalidPlanError(f"A tarefa {key} depende de si própria")

    remaining = {key: set(deps) for key, deps in dependencies.items()}
    dependents: dict[str, list[str]] = {key: [] for key in dependencies}
    for key, deps in dependencies.items():
        for dep in deps:
            dependents[dep].append(key)

    ready = deque(sorted(k for k, deps in remaining.items() if not deps))
    order: list[str] = []
    while ready:
        key = ready.popleft()
        order.append(key)
        for child in dependents[key]:
            remaining[child].discard(key)
            if not remaining[child]:
                ready.append(child)

    if len(order) != len(dependencies):
        stuck = sorted(set(dependencies) - set(order))
        raise InvalidPlanError(f"O plano tem dependências circulares entre: {', '.join(stuck)}")
    return order
