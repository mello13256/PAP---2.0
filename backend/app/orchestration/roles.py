"""Quem faz o quê, segundo a estratégia do run."""

from __future__ import annotations

from collections import Counter

from app.agents.models import Agent
from app.orchestration.context import RunContext
from app.orchestration.strategies import Assignment, ReviewPolicy
from app.tasks.models import Task


def _with_capability(agents: list[Agent], capability: str | None) -> list[Agent]:
    if not capability:
        return []
    return [a for a in agents if capability in (a.capabilities or [])]


def planner(ctx: RunContext) -> Agent:
    if ctx.strategy.assignment is Assignment.CAPABILITY:
        return (_with_capability(ctx.participants, "planning") or ctx.participants)[0]
    return ctx.participants[0]


def synthesizer(ctx: RunContext) -> Agent:
    if ctx.strategy.assignment is Assignment.CAPABILITY:
        return (_with_capability(ctx.participants, "synthesis") or [planner(ctx)])[0]
    return ctx.participants[0]


def executor(ctx: RunContext, task: Task, load: Counter) -> tuple[Agent, str]:
    """Devolve o agente e a razão da escolha (fica registada na tarefa)."""
    strategy = ctx.strategy
    if strategy.assignment is Assignment.FIRST_AGENT:
        return ctx.participants[0], "estratégia de agente único"
    if strategy.assignment is Assignment.SECOND_AGENT:
        agent = ctx.participants[1] if len(ctx.participants) > 1 else ctx.participants[0]
        return agent, "estratégia: o 2.º agente implementa todas as tarefas"

    candidates = _with_capability(ctx.participants, task.required_capability)
    if candidates:
        reason = f"tem a capacidade '{task.required_capability}'"
    else:
        candidates = list(ctx.participants)
        reason = "nenhum agente tem a capacidade pedida; escolhido o menos ocupado"
    agent = min(candidates, key=lambda a: (load[a.id], ctx.participants.index(a)))
    if len(candidates) > 1:
        reason += "; desempate: menos tarefas atribuídas"
    return agent, reason


def reviewer(ctx: RunContext, author: Agent) -> Agent | None:
    policy = ctx.strategy.review
    if policy is ReviewPolicy.NONE:
        return None
    if policy is ReviewPolicy.SELF:
        return author
    if policy is ReviewPolicy.FIRST_AGENT:
        return ctx.participants[0]
    others = [a for a in ctx.participants if a.id != author.id]
    if not others:
        return author
    return (_with_capability(others, "review") or others)[0]
