"""EventBus: publica o que acontece num run para a interface, em tempo real.

Dois tipos de eventos:

- **Persistentes** (``persist=True``): guardados em ``run_events`` com um id
  sequencial. Ex.: "mensagem criada", "tarefa concluída". Permitem que um
  browser que perdeu a ligação recupere o que falhou (Last-Event-ID) e que
  uma execução antiga seja revista (replay).
- **Transitórios** (``persist=False``): só para quem está a ver naquele momento.
  Ex.: cada fragmento de texto que um agente está a escrever. Guardá-los
  seriam milhares de linhas; a mensagem final completa fica em ``messages``.

Funciona dentro de um único processo (ver DT-02/análise: sem Redis).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic_core import to_jsonable_python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.types import utcnow
from app.runs.models import RunEvent

logger = logging.getLogger(__name__)

_QUEUE_SIZE = 2000


@dataclass(frozen=True, slots=True)
class Event:
    run_id: uuid.UUID
    type: str
    payload: dict[str, Any]
    created_at: datetime
    id: int | None = None  # None = transitório


@dataclass(eq=False)  # comparada por identidade (pode ser guardada num set)
class Subscription:
    run_id: uuid.UUID
    queue: asyncio.Queue[Event] = field(default_factory=lambda: asyncio.Queue(_QUEUE_SIZE))
    # Se o cliente não consumir a tempo e a fila encher, a subscrição termina;
    # o browser volta a ligar-se e recupera os eventos persistentes em falta.
    overflowed: bool = False


class EventBus:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker
        self._subscriptions: dict[uuid.UUID, set[Subscription]] = defaultdict(set)

    async def publish(
        self,
        run_id: uuid.UUID,
        type: str,
        payload: dict[str, Any] | None = None,
        *,
        persist: bool = True,
    ) -> Event:
        data = to_jsonable_python(payload or {})
        event_id = None
        created_at = utcnow()
        if persist:
            async with self._sessionmaker() as session:
                row = RunEvent(run_id=run_id, type=type, payload=data, created_at=created_at)
                session.add(row)
                await session.commit()
                event_id = row.id
        event = Event(run_id=run_id, type=type, payload=data, created_at=created_at, id=event_id)
        self._deliver(event)
        return event

    def _deliver(self, event: Event) -> None:
        for sub in list(self._subscriptions.get(event.run_id, ())):
            if sub.overflowed:
                continue
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Subscrição do run %s atrasada; a terminar", event.run_id)
                sub.overflowed = True

    @contextlib.contextmanager
    def subscribe(self, run_id: uuid.UUID) -> Iterator[Subscription]:
        sub = Subscription(run_id)
        self._subscriptions[run_id].add(sub)
        try:
            yield sub
        finally:
            subs = self._subscriptions.get(run_id)
            if subs is not None:
                subs.discard(sub)
                if not subs:
                    del self._subscriptions[run_id]

    def subscriber_count(self, run_id: uuid.UUID) -> int:
        return len(self._subscriptions.get(run_id, ()))
