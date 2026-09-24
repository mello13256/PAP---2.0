"""Uma "vez de falar" de um agente dentro de um run.

É o bloco básico da comunicação entre agentes, e o orquestrador (fase 10) vai
usá-lo. O agente nunca fala diretamente com outro agente: o sistema junta a
conversa do run (o que o utilizador e os outros agentes disseram), entrega-a ao
agente, transmite a resposta em tempo real e guarda-a como mensagem.

    Utilizador ─┐
    Granite ────┼──► mensagens do run (BD) ──► contexto ──► Qwen ──► nova mensagem
    Qwen ───────┘
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.factory import RuntimeFactory
from app.agents.models import Agent
from app.agents.runtime import CallContext
from app.events.bus import EventBus
from app.messages import service as messages
from app.messages.models import Message, MessageKind
from app.metrics.models import CallPurpose
from app.providers.base import ChatMessage, ProviderError, StreamCompleted, TextDelta
from app.providers.registry import UnknownProviderError
from app.runs.models import Run

logger = logging.getLogger(__name__)

TRANSCRIPT_MESSAGES = 20
TRANSCRIPT_CHARS_PER_MESSAGE = 4000


def build_transcript(history: list[Message], agent_names: dict[uuid.UUID, str]) -> str:
    lines = []
    for m in history:
        if m.sender_agent_id is not None:
            who = agent_names.get(m.sender_agent_id, "Agente")
        elif m.kind is MessageKind.USER:
            who = "Utilizador"
        else:
            who = "Sistema"
        content = m.content
        if len(content) > TRANSCRIPT_CHARS_PER_MESSAGE:
            content = content[:TRANSCRIPT_CHARS_PER_MESSAGE] + " […]"
        lines.append(f"[{who}]: {content}")
    return "\n\n".join(lines)


async def agent_turn(
    *,
    sessionmaker: async_sessionmaker[AsyncSession],
    bus: EventBus,
    factory: RuntimeFactory,
    run_id: uuid.UUID,
    agent_id: uuid.UUID,
    agent_names: dict[uuid.UUID, str],
) -> Message | None:
    """O agente lê a conversa do run e responde. Devolve a mensagem criada."""
    async with sessionmaker() as session:
        run = await session.get(Run, run_id)
        agent = await session.get(Agent, agent_id)
        if run is None or agent is None:
            return None
        history = await messages.list_messages(session, run_id, limit=TRANSCRIPT_MESSAGES)

        transcript = build_transcript(history, agent_names)
        prompt = (
            f"Objetivo do trabalho: {run.objective}\n\n"
            f"Conversa até agora:\n\n{transcript or '(ainda sem mensagens)'}\n\n"
            f"És o agente {agent.name}. Escreve a tua próxima intervenção na conversa."
        )
        turn_id = uuid.uuid4()
        await bus.publish(
            run_id,
            "agent.started",
            {"turn_id": turn_id, "agent_id": agent.id, "agent_name": agent.name},
            persist=False,
        )

        try:
            runtime = factory.build(agent)
            result = None
            async for event in runtime.stream(
                [ChatMessage.user(prompt)],
                context=CallContext(CallPurpose.EXECUTE, run_id=run_id),
            ):
                if isinstance(event, TextDelta):
                    await bus.publish(
                        run_id,
                        "agent.delta",
                        {"turn_id": turn_id, "agent_id": agent.id, "text": event.text},
                        persist=False,
                    )
                elif isinstance(event, StreamCompleted):
                    result = event.result
        except (ProviderError, UnknownProviderError) as exc:
            logger.warning("Agente %s falhou: %s", agent.name, exc)
            await messages.post_message(
                session,
                bus,
                run_id=run_id,
                kind=MessageKind.SYSTEM,
                content=f"O agente {agent.name} não conseguiu responder: {exc}",
                meta={"turn_id": str(turn_id), "agent_id": str(agent.id), "error": True},
            )
            return None

        return await messages.post_message(
            session,
            bus,
            run_id=run_id,
            kind=MessageKind.AGENT,
            content=result.text if result else "",
            sender_agent_id=agent.id,
            meta={
                "turn_id": str(turn_id),
                "model": result.model if result else agent.model,
                "input_tokens": result.usage.input_tokens if result else None,
                "output_tokens": result.usage.output_tokens if result else None,
            },
        )
