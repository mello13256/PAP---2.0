"""Execução de uma tarefa por um agente (primeira versão ou correção)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.models import Agent
from app.messages.models import MessageKind
from app.metrics.models import CallPurpose
from app.orchestration.agent_loop import run_agent_loop
from app.orchestration.context import RunContext
from app.orchestration.context_builder import build_task_context
from app.orchestration.tools import (
    LIST_FILES,
    READ_FILE,
    SEND_MESSAGE,
    SUBMIT_RESULT,
    WRITE_FILE,
    SubmitResultArgs,
    WorkspaceTools,
    parse_args,
)
from app.tasks import service as tasks_service
from app.tasks.models import Task


@dataclass
class ExecutionResult:
    summary: str
    changed: dict[str, int] = field(default_factory=dict)  # caminho → versão
    submitted: bool = False

    @property
    def ok(self) -> bool:
        return self.submitted or bool(self.changed)


async def execute_task(
    ctx: RunContext, task: Task, agent: Agent, *, feedback: str | None = None
) -> ExecutionResult:
    async with ctx.sessionmaker() as session:
        tasks = await tasks_service.list_tasks(session, ctx.run_id)
    current = next(t for t in tasks if t.id == task.id)
    built = await build_task_context(ctx, current, tasks, agent, feedback=feedback)
    toolbox = WorkspaceTools(
        ctx,
        agent,
        task.id,
        is_revision=feedback is not None,
        seen_versions=dict(built.shown_versions),
    )

    async def validate(arguments: dict[str, Any]) -> str:
        return parse_args(SubmitResultArgs, arguments).summary

    loop = await run_agent_loop(
        ctx,
        agent,
        prompt=built.text,
        tools=[LIST_FILES, READ_FILE, WRITE_FILE, SEND_MESSAGE, SUBMIT_RESULT],
        handlers=toolbox.handlers(),
        terminal_tool="submit_result",
        validate_terminal=validate,
        purpose=CallPurpose.REVISE if feedback else CallPurpose.EXECUTE,
        task_id=task.id,
        label=f"{task.key}{' (correção)' if feedback else ''}",
        max_steps=ctx.strategy.limits.max_tool_steps,
    )
    submitted = loop.output is not None
    summary = loop.output if submitted else (loop.text or "(o agente não entregou resumo)")
    result = ExecutionResult(summary=summary, changed=toolbox.changed, submitted=submitted)

    async with ctx.sessionmaker() as session:
        db_task = await session.get(Task, task.id)
        db_task.result = summary
        db_task.iteration_count += 1
        await session.commit()

    files = (
        ", ".join(f"{p} (v{v})" for p, v in toolbox.changed.items()) or "nenhum ficheiro alterado"
    )
    await ctx.say(
        MessageKind.TASK_RESULT,
        f"{task.key} — {summary}\n\nFicheiros: {files}",
        task_id=task.id,
        sender_agent_id=agent.id,
        meta={"files": toolbox.changed, "submitted": submitted, "revision": feedback is not None},
    )
    return result
