"""Tarefas em segundo plano (asyncio) com registo de erros.

Uma chamada a um LLM pode demorar segundos ou minutos. O pedido HTTP responde
logo (202) e o trabalho continua aqui. É preciso guardar uma referência a cada
tarefa, porque o asyncio só guarda referências fracas e uma tarefa "esquecida"
pode ser recolhida pelo garbage collector a meio.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)


class BackgroundTasks:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()

    def spawn(self, coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._on_done)
        return task

    def _on_done(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error(
                "Tarefa em segundo plano '%s' falhou", task.get_name(), exc_info=task.exception()
            )

    async def wait_all(self) -> None:
        """Espera que todas as tarefas terminem (usado nos testes)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def cancel_all(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*list(self._tasks), return_exceptions=True)
