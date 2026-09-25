"""Revisão estruturada de uma tarefa por outro agente."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.agents.models import Agent
from app.messages.models import MessageKind
from app.metrics.models import CallPurpose
from app.orchestration.agent_loop import run_agent_loop
from app.orchestration.context import RunContext
from app.orchestration.tools import (
    LIST_FILES,
    READ_FILE,
    SUBMIT_REVIEW,
    SubmitReviewArgs,
    WorkspaceTools,
    parse_args,
)
from app.reviews import service as reviews
from app.reviews.models import Severity, Verdict
from app.tasks.models import Task
from app.workspace import service as workspace
from app.workspace.models import ArtifactVersion

MAX_REVIEW_FILE_CHARS = 5_000

RUBRIC = """Avalia com espírito crítico, segundo esta rubrica:
1. Correção: o código/texto funciona e não tem erros evidentes?
2. Completude: cumpre TODOS os critérios de aceitação?
3. Coerência: é coerente com o objetivo e com o resto do projeto?
4. Qualidade: legível, organizado, sem duplicação desnecessária?
5. Segurança: há validação de dados, sem segredos no código, sem riscos óbvios?

Severidades: CRITICAL (não funciona / grave), MAJOR (falha um critério de aceitação),
MINOR (melhoria desejável), INFO (observação).
Usa NEEDS_REVISION se houver algum problema CRITICAL ou MAJOR; caso contrário APPROVED.
Indica sempre pelo menos uma observação, mesmo que seja INFO."""


@dataclass
class ReviewOutcome:
    verdict: Verdict
    summary: str
    issues: list[dict]

    def feedback(self) -> str:
        lines = [self.summary]
        for i in self.issues:
            where = f" [{i['file_path']}]" if i.get("file_path") else ""
            fix = f" → {i['suggestion']}" if i.get("suggestion") else ""
            lines.append(f"- {i['severity']}{where}: {i['description']}{fix}")
        return "\n".join(lines)


async def _changes_text(ctx: RunContext, task: Task, changed: dict[str, int]) -> str:
    blocks = []
    async with ctx.sessionmaker() as session:
        for path, version in changed.items():
            _, current = await workspace.read_file(session, ctx.project_id, path, version)
            first = await session.scalar(
                select(ArtifactVersion.version_number)
                .where(
                    ArtifactVersion.artifact_id == current.artifact_id,
                    ArtifactVersion.task_id == task.id,
                )
                .order_by(ArtifactVersion.version_number)
                .limit(1)
            )
            base = (first or version) - 1
            content = current.content
            if len(content) > MAX_REVIEW_FILE_CHARS:
                content = content[:MAX_REVIEW_FILE_CHARS] + "\n[… truncado: usa read_file]"
            block = f"## {path} (versão {version})\n```\n{content}\n```"
            if base > 0:
                diff = await workspace.diff(session, ctx.project_id, path, base, version)
                block += f"\nAlterações desde a versão {base}:\n```diff\n{diff[:2500]}\n```"
            blocks.append(block)
    return "\n\n".join(blocks) or "(a tarefa não alterou ficheiros)"


async def review_task(
    ctx: RunContext,
    task: Task,
    author: Agent,
    reviewer: Agent,
    changed: dict[str, int],
    round: int,
    previous: ReviewOutcome | None,
) -> ReviewOutcome | None:
    await ctx.say(
        MessageKind.ORCHESTRATOR,
        f"{reviewer.name} vai rever {task.key} (ronda {round}), feita por {author.name}.",
        task_id=task.id,
        recipient_agent_id=reviewer.id,
    )
    prompt = f"""# Objetivo geral
{ctx.objective}

# Tarefa a rever: {task.key} — {task.title}
{task.description}

Critérios de aceitação:
{task.acceptance_criteria or "(não definidos)"}

Autor: {author.name}
Resumo do autor: {task.result or "(sem resumo)"}

# Trabalho produzido
{await _changes_text(ctx, task, changed)}
"""
    if previous is not None:
        prompt += f"\n# Revisão anterior (ronda {round - 1})\n{previous.feedback()}\n"
        prompt += "Verifica se os problemas anteriores foram corrigidos.\n"
    prompt += (
        f"\n# Como rever\n{RUBRIC}\n"
        "Podes usar read_file para ver outros ficheiros. Termina com `submit_review`."
    )

    async def validate(arguments: dict[str, Any]) -> SubmitReviewArgs:
        return parse_args(SubmitReviewArgs, arguments)

    toolbox = WorkspaceTools(ctx, reviewer, task.id)
    handlers = {k: v for k, v in toolbox.handlers().items() if k in ("list_files", "read_file")}
    loop = await run_agent_loop(
        ctx,
        reviewer,
        prompt=prompt,
        tools=[LIST_FILES, READ_FILE, SUBMIT_REVIEW],
        handlers=handlers,
        terminal_tool="submit_review",
        validate_terminal=validate,
        purpose=CallPurpose.REVIEW,
        task_id=task.id,
        label=f"revisão de {task.key}",
        max_steps=4,
    )
    submission: SubmitReviewArgs | None = loop.output
    if submission is None:
        await ctx.say(
            MessageKind.SYSTEM,
            f"{reviewer.name} não entregou uma revisão válida para {task.key}.",
            task_id=task.id,
        )
        return None

    issues = [
        {
            "severity": i.severity,
            "file_path": i.file,
            "description": i.description,
            "suggestion": i.suggestion,
        }
        for i in submission.issues
    ]
    verdict = reviews.effective_verdict(submission.verdict, [i.severity for i in submission.issues])
    async with ctx.sessionmaker() as session:
        review = await reviews.create_review(
            session,
            task_id=task.id,
            round=round,
            reviewer_id=reviewer.id,
            author_id=author.id,
            verdict=verdict,
            summary=submission.summary,
            issues=issues,
            reviewed_versions=[f"{p}@v{v}" for p, v in changed.items()],
        )
    outcome = ReviewOutcome(verdict, submission.summary, issues)
    note = ""
    if verdict is not submission.verdict:
        note = (
            "\n(O revisor escreveu APPROVED, mas apontou problemas graves: "
            "tratado como NEEDS_REVISION.)"
        )
    await ctx.say(
        MessageKind.REVIEW,
        f"Revisão de {task.key} (ronda {round}): {verdict}\n{outcome.feedback()}{note}",
        task_id=task.id,
        sender_agent_id=reviewer.id,
        recipient_agent_id=author.id,
        meta={"review_id": str(review.id), "verdict": verdict, "round": round},
    )
    await ctx.event(
        "review.completed",
        {
            "task_id": task.id,
            "task_key": task.key,
            "round": round,
            "verdict": verdict,
            "reviewer_id": reviewer.id,
            "issues": len(issues),
            "blocking": sum(
                1 for i in issues if i["severity"] in (Severity.CRITICAL, Severity.MAJOR)
            ),
        },
    )
    return outcome
