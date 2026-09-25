"""Métricas agregadas de um run, calculadas a partir dos dados reais guardados."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.types import utcnow
from app.decisions.models import Decision
from app.interventions.models import Intervention
from app.metrics.models import LLMCall, RunMetrics
from app.reviews.models import Review, Verdict
from app.runs.models import Run
from app.tasks.models import Task, TaskStatus


async def compute_run_metrics(session: AsyncSession, run_id: uuid.UUID) -> RunMetrics:
    run = await session.get(Run, run_id)
    calls = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(LLMCall.input_tokens), 0),
                func.coalesce(func.sum(LLMCall.output_tokens), 0),
                func.sum(LLMCall.estimated_cost_usd),
                func.count(LLMCall.estimated_cost_usd),
            ).where(LLMCall.run_id == run_id)
        )
    ).one()
    failed = await session.scalar(
        select(func.count())
        .select_from(LLMCall)
        .where(LLMCall.run_id == run_id, LLMCall.success.is_(False))
    )
    statuses = dict(
        (
            await session.execute(
                select(Task.status, func.count()).where(Task.run_id == run_id).group_by(Task.status)
            )
        ).all()
    )
    review_rows = (
        await session.execute(
            select(Review.verdict, func.count())
            .join(Task, Task.id == Review.task_id)
            .where(Task.run_id == run_id)
            .group_by(Review.verdict)
        )
    ).all()
    reviews_by_verdict = dict(review_rows)
    decisions = await session.scalar(
        select(func.count()).select_from(Decision).where(Decision.run_id == run_id)
    )
    interventions = await session.scalar(
        select(func.count()).select_from(Intervention).where(Intervention.run_id == run_id)
    )

    end = run.finished_at or utcnow()
    elapsed = (end - run.started_at).total_seconds() if run.started_at else 0.0
    total_calls, input_tokens, output_tokens, cost_sum, cost_count = calls
    metrics = await session.get(RunMetrics, run_id) or RunMetrics(run_id=run_id)
    metrics.execution_time_s = round(elapsed, 1)
    metrics.api_calls = total_calls or 0
    metrics.failed_calls = failed or 0
    metrics.input_tokens = int(input_tokens or 0)
    metrics.output_tokens = int(output_tokens or 0)
    metrics.tasks_total = sum(statuses.values())
    metrics.tasks_completed = statuses.get(TaskStatus.COMPLETED, 0)
    metrics.tasks_failed = statuses.get(TaskStatus.FAILED, 0)
    metrics.reviews = sum(reviews_by_verdict.values())
    metrics.revisions = reviews_by_verdict.get(Verdict.NEEDS_REVISION, 0)
    metrics.decisions = decisions or 0
    metrics.human_interventions = interventions or 0
    # Custo só é conhecido se TODAS as chamadas tiverem preço conhecido.
    metrics.estimated_cost_usd = (
        round(float(cost_sum or 0), 6) if cost_count == total_calls else None
    )
    metrics.final_status = str(run.status)
    metrics.computed_at = utcnow()
    session.add(metrics)
    await session.commit()
    return metrics
