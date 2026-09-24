"""Formato Server-Sent Events (SSE).

Cada evento é texto simples:

    id: 42
    event: message.created
    data: {"id": "...", "content": "..."}

O browser (EventSource) volta a ligar-se sozinho se a ligação cair e envia o
último ``id`` recebido no cabeçalho ``Last-Event-ID``.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.events.bus import Event, EventBus
from app.runs.models import RunEvent

HEARTBEAT_S = 15.0


def format_sse(event: Event) -> str:
    lines = []
    if event.id is not None:
        lines.append(f"id: {event.id}")
    lines.append(f"event: {event.type}")
    body = {"type": event.type, "created_at": event.created_at.isoformat(), **event.payload}
    lines.append(f"data: {json.dumps(body, ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


async def stored_events(
    sessionmaker: async_sessionmaker[AsyncSession], run_id: uuid.UUID, after_id: int
) -> Sequence[Event]:
    async with sessionmaker() as session:
        rows = await session.scalars(
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.id > after_id)
            .order_by(RunEvent.id)
        )
        return [
            Event(run_id=r.run_id, type=r.type, payload=r.payload, created_at=r.created_at, id=r.id)
            for r in rows
        ]


async def event_stream(
    bus: EventBus,
    sessionmaker: async_sessionmaker[AsyncSession],
    run_id: uuid.UUID,
    *,
    last_event_id: int = 0,
    follow: bool = True,
    heartbeat_s: float = HEARTBEAT_S,
) -> AsyncIterator[str]:
    """Primeiro envia os eventos guardados em falta, depois os novos em tempo real."""

    # Subscreve ANTES de ler a BD, para não perder eventos publicados entretanto.
    with bus.subscribe(run_id) as sub:
        last = last_event_id
        for event in await stored_events(sessionmaker, run_id, last):
            yield format_sse(event)
            last = event.id or last
        if not follow:
            return

        yield "retry: 3000\n\n"  # o browser espera 3 s antes de voltar a ligar
        while not sub.overflowed:
            try:
                event = await asyncio.wait_for(sub.queue.get(), timeout=heartbeat_s)
            except TimeoutError:
                yield ": ping\n\n"  # comentário SSE: mantém a ligação viva
                continue
            if event.id is not None:
                if event.id <= last:
                    continue  # já enviado no replay
                last = event.id
            yield format_sse(event)
