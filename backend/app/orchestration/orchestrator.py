"""O orquestrador: conduz um run do início ao fim.

    PLANNING ──► RUNNING ────────────────────────────────► FINALIZING ──► COMPLETED
                   │ enquanto houver tarefas prontas:                       (ou FAILED /
                   │   atribuir → executar → rever → (corrigir → rever)*     CANCELLED)
                   │ antes de cada passo: pausa? cancelado? limites?

Só o orquestrador decide o passo seguinte; os agentes apenas respondem ao que
lhes é pedido. É isso que impede ciclos infinitos.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter

from app.db.types import utcnow
from app.messages.models import MessageKind
from app.metrics.models import CallPurpose
from app.metrics.service import compute_run_metrics
from app.orchestration import roles
from app.orchestration.agent_loop import run_agent_loop
from app.orchestration.context import LimitExceeded, RunContext
from app.orchestration.executor import execute_task
from app.orchestration.planner import plan
from app.orchestration.review import ReviewOutcome, review_task
from app.orchestration.tools import SUBMIT_RESULT, SubmitResultArgs, parse_args
from app.providers.base import ProviderError, ProviderErrorKind
from app.providers.registry import UnknownProviderError
from app.reviews.models import Verdict
from app.runs.models import Run, RunStatus
from app.tasks import service as tasks_service
from app.tasks.models import Task, TaskStatus
from app.tasks.state import FINISHED

logger = logging.getLogger(__name__)


async def set_run_status(ctx: RunContext, status: RunStatus, **fields) -> None:
    async with ctx.sessionmaker() as session:
        run = await session.get(Run, ctx.run_id)
        run.status = status
        for key, value in fields.items():
            setattr(run, key, value)
        await session.commit()
    await ctx.event("run.status", {"status": status, **{k: v for k, v in fields.items()}})


async def set_task_status(ctx: RunContext, task: Task, status: TaskStatus, **fields) -> Task:
    async with ctx.sessionmaker() as session:
        updated = await tasks_service.set_status(session, task.id, status, **fields)
        tasks = await tasks_service.list_tasks(session, ctx.run_id)
    fresh = next(t for t in tasks if t.id == updated.id)
    await ctx.event("task.updated", tasks_service.to_out(fresh).model_dump(mode="json"))
    return fresh


async def run_task(ctx: RunContext, task: Task, load: Counter) -> None:
    author, reason = roles.executor(ctx, task, load)
    load[author.id] += 1
    task = await set_task_status(
        ctx, task, TaskStatus.RUNNING, assigned_agent_id=author.id, assignment_reason=reason
    )
    await ctx.say(
        MessageKind.ORCHESTRATOR,
        f"{task.key} «{task.title}» atribuída a {author.name} ({reason}).",
        task_id=task.id,
        recipient_agent_id=author.id,
    )

    execution = await execute_task(ctx, task, author)
    if not execution.ok:
        await set_task_status(ctx, task, TaskStatus.FAILED)
        await ctx.say(
            MessageKind.SYSTEM,
            f"{task.key} falhou: {author.name} não produziu resultado.",
            task_id=task.id,
        )
        return

    reviewer = roles.reviewer(ctx, author)
    if reviewer is None:
        await set_task_status(ctx, task, TaskStatus.COMPLETED)
        return

    changed = dict(execution.changed)
    previous: ReviewOutcome | None = None
    max_rounds = ctx.strategy.limits.max_review_rounds
    for round in range(1, max_rounds + 1):
        task = await set_task_status(ctx, task, TaskStatus.REVIEW)
        outcome = await review_task(ctx, task, author, reviewer, changed, round, previous)
        if outcome is None:
            await set_task_status(ctx, task, TaskStatus.COMPLETED)
            return
        if outcome.verdict is Verdict.APPROVED:
            await set_task_status(ctx, task, TaskStatus.COMPLETED)
            return
        if round == max_rounds:
            await set_task_status(ctx, task, TaskStatus.COMPLETED)
            await ctx.say(
                MessageKind.SYSTEM,
                f"{task.key} concluída com problemas por resolver: atingido o limite de "
                f"{max_rounds} rondas de revisão.",
                task_id=task.id,
            )
            return

        task = await set_task_status(ctx, task, TaskStatus.RUNNING)
        await ctx.say(
            MessageKind.ORCHESTRATOR,
            f"{author.name}, corrige {task.key} de acordo com a revisão de {reviewer.name}.",
            task_id=task.id,
            recipient_agent_id=author.id,
        )
        revision = await execute_task(ctx, task, author, feedback=outcome.feedback())
        if not revision.changed:
            await set_task_status(ctx, task, TaskStatus.COMPLETED)
            await ctx.say(
                MessageKind.SYSTEM,
                f"{task.key}: a correção não alterou nenhum ficheiro. Ciclo de revisão terminado "
                "(sem progresso).",
                task_id=task.id,
            )
            return
        changed.update(revision.changed)
        previous = outcome


async def finalize(ctx: RunContext, tasks: list[Task]) -> str:
    agent = roles.synthesizer(ctx)
    lines = [f"- {t.key} [{t.status}] {t.title}: {(t.result or '')[:600]}" for t in tasks]
    prompt = (
        f"# Objetivo\n{ctx.objective}\n\n# Tarefas realizadas\n"
        + "\n".join(lines)
        + "\n\n# O que tens de fazer\n"
        "Escreve o relatório final para o utilizador: o que foi feito, "
        "que ficheiros existem e para que servem, como usar o resultado e o que ficou por fazer. "
        "Entrega-o com `submit_result`."
    )

    async def validate(arguments):
        return parse_args(SubmitResultArgs, arguments).summary

    loop = await run_agent_loop(
        ctx,
        agent,
        prompt=prompt,
        tools=[SUBMIT_RESULT],
        handlers={},
        terminal_tool="submit_result",
        validate_terminal=validate,
        purpose=CallPurpose.FINALIZE,
        label="relatório final",
        max_steps=3,
    )
    return loop.output or loop.text or "(não foi possível gerar o relatório final)"


async def execute_run(ctx: RunContext) -> None:
    """Conduz o run inteiro. Nunca lança exceções: o resultado fica no estado do run."""
    try:
        await set_run_status(ctx, RunStatus.PLANNING, started_at=utcnow())
        await plan(ctx)
        await set_run_status(ctx, RunStatus.RUNNING)

        load: Counter = Counter()
        while True:
            await ctx.checkpoint()
            async with ctx.sessionmaker() as session:
                tasks = await tasks_service.list_tasks(session, ctx.run_id)
            for blocked in tasks_service.blocked_tasks(tasks):
                await set_task_status(ctx, blocked, TaskStatus.CANCELLED)
                await ctx.say(
                    MessageKind.SYSTEM,
                    f"{blocked.key} cancelada: depende de uma tarefa que falhou.",
                    task_id=blocked.id,
                )
            ready = tasks_service.ready_tasks(tasks)
            if not ready:
                break
            # Uma tarefa de cada vez: com uma GPU de 8 GB só cabe um modelo carregado.
            await run_task(ctx, ready[0], load)

        await set_run_status(ctx, RunStatus.FINALIZING)
        async with ctx.sessionmaker() as session:
            tasks = await tasks_service.list_tasks(session, ctx.run_id)
        report = await finalize(ctx, tasks)
        failed = [t.key for t in tasks if t.status is not TaskStatus.COMPLETED]
        await ctx.say(MessageKind.ORCHESTRATOR, f"Relatório final:\n{report}")
        if failed:
            await set_run_status(
                ctx,
                RunStatus.FAILED,
                finished_at=utcnow(),
                final_result=report,
                failure_reason=f"Tarefas não concluídas: {', '.join(failed)}",
            )
        else:
            await set_run_status(
                ctx, RunStatus.COMPLETED, finished_at=utcnow(), final_result=report
            )
    except LimitExceeded as exc:
        await ctx.say(MessageKind.SYSTEM, f"Run interrompido: {exc}")
        await _stop(ctx, RunStatus.FAILED, str(exc))
    except (ProviderError, UnknownProviderError) as exc:
        hint = ""
        if getattr(exc, "kind", None) is ProviderErrorKind.UNAVAILABLE:
            hint = " Confirma que o Ollama (ou o fornecedor) está a correr."
        reason = f"Um agente não conseguiu responder: {exc}.{hint}"
        await ctx.say(MessageKind.SYSTEM, reason)
        await _stop(ctx, RunStatus.FAILED, reason)
    except asyncio.CancelledError:
        await asyncio.shield(_stop(ctx, RunStatus.CANCELLED, "Cancelado pelo utilizador"))
    except Exception as exc:  # erro inesperado: fica registado em vez de desaparecer
        logger.exception("Run %s falhou", ctx.run_id)
        await _stop(ctx, RunStatus.FAILED, f"Erro interno: {type(exc).__name__}: {exc}")
    finally:
        async with ctx.sessionmaker() as session:
            metrics = await compute_run_metrics(session, ctx.run_id)
        await ctx.event(
            "run.finished",
            {
                "metrics": {
                    "api_calls": metrics.api_calls,
                    "execution_time_s": metrics.execution_time_s,
                    "tasks_completed": metrics.tasks_completed,
                    "tasks_total": metrics.tasks_total,
                }
            },
        )


async def _stop(ctx: RunContext, status: RunStatus, reason: str) -> None:
    async with ctx.sessionmaker() as session:
        tasks = await tasks_service.list_tasks(session, ctx.run_id)
        for task in tasks:
            if task.status not in FINISHED:
                task.status = TaskStatus.CANCELLED
                task.completed_at = utcnow()
        await session.commit()
    await set_run_status(ctx, status, finished_at=utcnow(), failure_reason=reason)
