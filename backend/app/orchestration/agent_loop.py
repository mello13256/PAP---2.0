"""Ciclo de trabalho de um agente com ferramentas.

    prompt ─► modelo ─► pede ferramentas ─► sistema executa ─► resultados ─► modelo ...
              └── até chamar a ferramenta "terminal"
                  (submit_result / submit_plan / submit_review)

É o mesmo ciclo para planear, executar e rever; muda o prompt e as ferramentas.
Tudo o que o agente escreve é transmitido em tempo real (agent.delta) e cada
ferramenta usada fica registada (tool.called).

Proteções:
- número máximo de passos (``max_steps``);
- se o modelo responder só com texto, é lembrado de usar as ferramentas (no
  máximo 2 vezes); depois o ciclo termina com o texto que houver;
- argumentos inválidos são devolvidos ao modelo como erro, para ele corrigir.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.agents.models import Agent
from app.agents.runtime import CallContext
from app.messages.models import MessageKind
from app.metrics.models import CallPurpose
from app.orchestration.context import RunContext
from app.orchestration.tools import ToolError
from app.providers.base import (
    ChatMessage,
    StreamCompleted,
    TextDelta,
    ToolCall,
    ToolCallStarted,
    ToolChoice,
    ToolChoiceMode,
    ToolSpec,
)

Handler = Callable[[dict[str, Any]], Awaitable[str]]
# Valida os argumentos da ferramenta terminal; devolve o objeto validado ou lança ToolError.
TerminalValidator = Callable[[dict[str, Any]], Awaitable[Any]]

MAX_NUDGES = 2


@dataclass
class LoopResult:
    output: Any | None  # resultado validado da ferramenta terminal (None se não foi chamada)
    text: str  # último texto escrito pelo agente
    steps: int


def _short(value: Any, limit: int = 300) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


async def run_agent_loop(
    ctx: RunContext,
    agent: Agent,
    *,
    prompt: str,
    tools: Sequence[ToolSpec],
    handlers: dict[str, Handler],
    terminal_tool: str,
    validate_terminal: TerminalValidator,
    purpose: CallPurpose,
    task_id: uuid.UUID | None = None,
    label: str = "",
    max_steps: int = 10,
) -> LoopResult:
    runtime = ctx.runtimes[agent.id]
    messages: list[ChatMessage] = [ChatMessage.user(prompt)]
    last_text = ""
    nudges = 0

    for step in range(1, max_steps + 1):
        await ctx.checkpoint()
        turn_id = uuid.uuid4()
        await ctx.event(
            "agent.started",
            {
                "turn_id": turn_id,
                "agent_id": agent.id,
                "agent_name": agent.name,
                "task_id": task_id,
                "label": label,
            },
            persist=False,
        )
        result = None
        async for event in runtime.stream(
            messages,
            context=CallContext(purpose, run_id=ctx.run_id, task_id=task_id),
            tools=tools,
            tool_choice=ToolChoice(ToolChoiceMode.REQUIRED),
        ):
            if isinstance(event, TextDelta):
                await ctx.event(
                    "agent.delta",
                    {
                        "turn_id": turn_id,
                        "agent_id": agent.id,
                        "task_id": task_id,
                        "text": event.text,
                    },
                    persist=False,
                )
            elif isinstance(event, ToolCallStarted):
                await ctx.event(
                    "tool.started",
                    {
                        "turn_id": turn_id,
                        "agent_id": agent.id,
                        "task_id": task_id,
                        "name": event.name,
                    },
                    persist=False,
                )
            elif isinstance(event, StreamCompleted):
                result = event.result

        text = result.text.strip()
        if text and not result.tool_calls_from_text:
            last_text = text
            await ctx.say(
                MessageKind.AGENT,
                text,
                task_id=task_id,
                sender_agent_id=agent.id,
                meta={"label": label},
            )
        messages.append(ChatMessage.from_result(result))

        if not result.tool_calls:
            nudges += 1
            if nudges > MAX_NUDGES:
                return LoopResult(None, last_text, step)
            messages.append(
                ChatMessage.user(
                    f"Não chamaste nenhuma ferramenta. Usa as ferramentas disponíveis e termina "
                    f"chamando `{terminal_tool}`."
                )
            )
            continue

        # Ferramentas normais primeiro; a terminal no fim.
        calls: list[ToolCall] = sorted(result.tool_calls, key=lambda c: c.name == terminal_tool)
        for call in calls:
            if call.name == terminal_tool:
                try:
                    output = await validate_terminal(call.arguments)
                except ToolError as exc:
                    await _record_tool(ctx, agent, task_id, call, ok=False, output=str(exc))
                    messages.append(ChatMessage.tool_result(call.id, str(exc), is_error=True))
                    continue
                await _record_tool(ctx, agent, task_id, call, ok=True, output="entregue")
                return LoopResult(output, last_text, step)

            handler = handlers.get(call.name)
            if handler is None:
                available = ", ".join([*handlers, terminal_tool])
                messages.append(
                    ChatMessage.tool_result(
                        call.id,
                        f"Ferramenta desconhecida: {call.name}. Disponíveis: {available}",
                        is_error=True,
                    )
                )
                continue
            try:
                output = await handler(call.arguments)
                ok = True
            except ToolError as exc:
                output, ok = str(exc), False
            await _record_tool(ctx, agent, task_id, call, ok=ok, output=output)
            messages.append(ChatMessage.tool_result(call.id, output, is_error=not ok))

    return LoopResult(None, last_text, max_steps)


async def _record_tool(
    ctx: RunContext,
    agent: Agent,
    task_id: uuid.UUID | None,
    call: ToolCall,
    *,
    ok: bool,
    output: str,
) -> None:
    args = {k: (_short(v, 120) if k == "content" else _short(v)) for k, v in call.arguments.items()}
    await ctx.event(
        "tool.called",
        {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "task_id": task_id,
            "name": call.name,
            "arguments": args,
            "ok": ok,
            "output": _short(output),
        },
    )
