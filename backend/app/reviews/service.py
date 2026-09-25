from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.reviews.models import Review, ReviewIssue, Severity, Verdict
from app.reviews.schemas import ReviewIssueOut, ReviewOut
from app.tasks.models import Task

BLOCKING = {Severity.CRITICAL, Severity.MAJOR}


def effective_verdict(verdict: Verdict, severities: Sequence[Severity]) -> Verdict:
    """Regra de consistência: não confiamos cegamente no revisor.

    Se ele próprio aponta um problema CRITICAL ou MAJOR, a tarefa volta para
    correção, mesmo que tenha escrito APPROVED.
    """
    if any(s in BLOCKING for s in severities):
        return Verdict.NEEDS_REVISION
    return verdict


async def create_review(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    round: int,
    reviewer_id: uuid.UUID,
    author_id: uuid.UUID,
    verdict: Verdict,
    summary: str,
    issues: Sequence[dict],
    reviewed_versions: list[str],
) -> Review:
    review = Review(
        task_id=task_id,
        round=round,
        reviewer_agent_id=reviewer_id,
        author_agent_id=author_id,
        verdict=verdict,
        summary=summary,
        reviewed_versions=reviewed_versions,
    )
    session.add(review)
    await session.flush()
    for issue in issues:
        session.add(ReviewIssue(review_id=review.id, **issue))
    await session.commit()
    return review


async def list_reviews(session: AsyncSession, run_id: uuid.UUID) -> list[ReviewOut]:
    rows = (
        await session.execute(
            select(Review, Task.key)
            .join(Task, Task.id == Review.task_id)
            .where(Task.run_id == run_id)
            .order_by(Review.created_at)
        )
    ).all()
    out = []
    for review, key in rows:
        issues = await session.scalars(
            select(ReviewIssue)
            .where(ReviewIssue.review_id == review.id)
            .order_by(ReviewIssue.created_at)
        )
        out.append(
            ReviewOut(
                id=review.id,
                task_id=review.task_id,
                task_key=key,
                round=review.round,
                reviewer_agent_id=review.reviewer_agent_id,
                author_agent_id=review.author_agent_id,
                verdict=review.verdict,
                summary=review.summary,
                reviewed_versions=review.reviewed_versions,
                human_override=review.human_override,
                human_comment=review.human_comment,
                issues=[ReviewIssueOut.model_validate(i) for i in issues],
                created_at=review.created_at,
            )
        )
    return out
