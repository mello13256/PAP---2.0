"""Planeamento: transforma o objetivo num grafo de tarefas."""

from __future__ import annotations

import logging
from typing import Any

from app.messages.models import MessageKind
from app.metrics.models import CallPurpose
from app.orchestration import roles
from app.orchestration.agent_loop import run_agent_loop
from app.orchestration.context import RunContext
from app.orchestration.tools import SUBMIT_PLAN, SubmitPlanArgs, ToolError, parse_args
from app.tasks import service as tasks_service
from app.tasks.graph import InvalidPlanError
from app.tasks.models import Task
from app.tasks.schemas import PlannedTask

logger = logging.getLogger(__name__)

CAPABILITIES = "planning, architecture, coding, review, testing, documentation, synthesis"


def planning_prompt(ctx: RunContext) -> str:
    team = "\n".join(
        f"- {a.name}: {', '.join(a.capabilities or []) or 'sem capacidades definidas'}"
        for a in ctx.participants
    )
    limit = ctx.strategy.limits.max_tasks
    return f"""# Objetivo
{ctx.objective}

# Equipa
{team}

# O que tens de fazer
Divide o objetivo em tarefas concretas (entre 2 e {limit}) e entrega o plano com `submit_plan`.

Regras:
- Cada tarefa tem: key (T1, T2, ...), title, description (o que fazer e que ficheiros criar),
  acceptance_criteria (como saber que está bem feita), required_capability (uma de: {CAPABILITIES})
  e depends_on (lista de keys de tarefas que têm de terminar antes).
- As dependências não podem formar ciclos.
- Cada tarefa deve produzir ficheiros concretos no projeto.
- NÃO cries tarefas só para "rever": todas as tarefas são revistas automaticamente.
- Prefere poucas tarefas bem definidas a muitas tarefas vagas."""


async def plan(ctx: RunContext) -> list[Task]:
    agent = roles.planner(ctx)
    await ctx.say(
        MessageKind.ORCHESTRATOR,
        f"{agent.name} vai analisar o objetivo e propor um plano.",
        recipient_agent_id=agent.id,
    )

    async def validate(arguments: dict[str, Any]) -> list[PlannedTask]:
        planned = parse_args(SubmitPlanArgs, arguments).tasks
        try:
            tasks_service.validate_plan(planned, max_tasks=ctx.strategy.limits.max_tasks)
        except InvalidPlanError as exc:
            raise ToolError(f"Plano inválido: {exc.message}. Corrige e volta a submeter.") from None
        return planned

    result = await run_agent_loop(
        ctx,
        agent,
        prompt=planning_prompt(ctx),
        tools=[SUBMIT_PLAN],
        handlers={},
        terminal_tool="submit_plan",
        validate_terminal=validate,
        purpose=CallPurpose.PLAN,
        label="planeamento",
        max_steps=4,
    )
    planned: list[PlannedTask] | None = result.output
    if planned is None:
        planned = [
            PlannedTask(
                key="T1",
                title="Realizar o objetivo",
                description=ctx.objective,
                acceptance_criteria="O objetivo está cumprido.",
                required_capability="coding",
            )
        ]
        await ctx.say(
            MessageKind.SYSTEM,
            f"{agent.name} não entregou um plano válido. O orquestrador usou um plano de "
            "uma só tarefa.",
        )

    async with ctx.sessionmaker() as session:
        await tasks_service.create_tasks(
            session,
            run_id=ctx.run_id,
            project_id=ctx.project_id,
            planned=planned,
            max_iterations=ctx.strategy.limits.max_review_rounds + 1,
        )
        tasks = await tasks_service.list_tasks(session, ctx.run_id)

    summary = "\n".join(
        f"{t.key}. {t.title}"
        + (f"  (depois de {', '.join(d.key for d in t.dependencies)})" if t.dependencies else "")
        for t in tasks
    )
    await ctx.say(
        MessageKind.ORCHESTRATOR,
        f"Plano aceite com {len(tasks)} tarefas:\n{summary}",
        meta={"planner_id": str(agent.id)},
    )
    await ctx.event(
        "plan.created", {"tasks": [tasks_service.to_out(t).model_dump(mode="json") for t in tasks]}
    )
    return tasks
