"""Constrói o contexto (a "memória") de cada chamada.

Os LLMs não se lembram de nada entre chamadas. Tudo o que um agente sabe numa
tarefa é montado aqui a partir da BD, por ordem de prioridade e dentro de um
orçamento de caracteres (os modelos locais têm janelas de contexto pequenas):

 1. objetivo, plano e a tarefa (sempre)
 2. revisão a corrigir (se for uma correção)
 3. instruções do utilizador e mensagens de outros agentes para este agente
 4. resultados (resumos) das tarefas de que depende
 5. conteúdo dos ficheiros relevantes (o que cabe; o resto via read_file)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import or_, select

from app.agents.models import Agent
from app.messages.models import Message, MessageKind
from app.orchestration.context import RunContext
from app.tasks.models import Task
from app.workspace import service as workspace
from app.workspace.models import Artifact, ArtifactVersion

BUDGET_CHARS = 14_000
MAX_FILE_CHARS = 5_000
MAX_RESULT_CHARS = 1_500


@dataclass
class BuiltContext:
    text: str
    shown_versions: dict[str, int] = field(default_factory=dict)  # ficheiros incluídos


def _plan_overview(tasks: list[Task], names: dict[uuid.UUID, str]) -> str:
    lines = []
    for t in tasks:
        who = names.get(t.assigned_agent_id, "—") if t.assigned_agent_id else "—"
        deps = f" (depende de {', '.join(d.key for d in t.dependencies)})" if t.dependencies else ""
        lines.append(f"- {t.key} [{t.status}] {t.title} — {who}{deps}")
    return "\n".join(lines)


async def relevant_files(
    ctx: RunContext, task_ids: set[uuid.UUID]
) -> list[tuple[Artifact, ArtifactVersion]]:
    """Versão atual dos ficheiros alterados pelas tarefas indicadas."""
    if not task_ids:
        return []
    async with ctx.sessionmaker() as session:
        artifact_ids = set(
            await session.scalars(
                select(ArtifactVersion.artifact_id).where(ArtifactVersion.task_id.in_(task_ids))
            )
        )
        files = await workspace.list_files(session, ctx.project_id)
    return [(a, v) for a, v in files if a.id in artifact_ids]


async def build_task_context(
    ctx: RunContext, task: Task, tasks: list[Task], agent: Agent, *, feedback: str | None = None
) -> BuiltContext:
    names = ctx.names
    parts: list[str] = [
        f"# Objetivo geral\n{ctx.objective}",
        f"# Plano da equipa\n{_plan_overview(tasks, names)}",
        f"# A tua tarefa: {task.key} — {task.title}\n{task.description}"
        + (
            f"\n\nCritérios de aceitação:\n{task.acceptance_criteria}"
            if task.acceptance_criteria
            else ""
        ),
    ]
    if feedback:
        parts.append(
            "# Revisão a corrigir\nOutro agente reviu o teu trabalho e pediu alterações. "
            f"Corrige TODOS os problemas indicados:\n{feedback}"
        )

    async with ctx.sessionmaker() as session:
        notes = list(
            await session.scalars(
                select(Message)
                .where(
                    Message.run_id == ctx.run_id,
                    or_(
                        Message.kind == MessageKind.USER,
                        Message.recipient_agent_id == agent.id,
                    ),
                )
                .order_by(Message.created_at.desc())
                .limit(6)
            )
        )
    if notes:
        lines = []
        for m in reversed(notes):
            who = (
                "Utilizador"
                if m.kind is MessageKind.USER
                else names.get(m.sender_agent_id, "Agente")
            )
            lines.append(f"[{who}]: {m.content[:800]}")
        parts.append("# Mensagens e instruções para ti\n" + "\n".join(lines))

    deps = list(task.dependencies)
    if deps:
        results = [
            f"## {d.key} — {d.title}\n{(d.result or '(sem resumo)')[:MAX_RESULT_CHARS]}"
            for d in deps
        ]
        parts.append("# Resultados das tarefas de que dependes\n" + "\n\n".join(results))

    async with ctx.sessionmaker() as session:
        all_files = await workspace.list_files(session, ctx.project_id)
    if all_files:
        parts.append(
            "# Ficheiros do projeto\n"
            + "\n".join(f"- {a.path} (versão {v.version_number})" for a, v in all_files)
        )

    built = BuiltContext("")
    used = sum(len(p) for p in parts)
    relevant = await relevant_files(ctx, {d.id for d in deps} | {task.id})
    file_parts = []
    for artifact, version in relevant:
        content = version.content
        truncated = len(content) > MAX_FILE_CHARS
        if truncated:
            content = (
                content[:MAX_FILE_CHARS] + "\n[… ficheiro truncado: usa read_file para o ler todo]"
            )
        block = f"## {artifact.path} (versão {version.version_number})\n```\n{content}\n```"
        if used + len(block) > BUDGET_CHARS:
            file_parts.append(
                f"## {artifact.path}: não incluído por falta de espaço (usa read_file)"
            )
            continue
        used += len(block)
        file_parts.append(block)
        if not truncated:
            built.shown_versions[artifact.path] = version.version_number
    if file_parts:
        parts.append("# Conteúdo de ficheiros relevantes\n" + "\n\n".join(file_parts))

    colleagues = ", ".join(a.name for a in ctx.participants if a.id != agent.id) or "nenhum"
    parts.append(
        "# Como trabalhar\n"
        "- Cria/altera ficheiros com `write_file`, sempre com o conteúdo COMPLETO do ficheiro.\n"
        "- Para alterar um ficheiro que não está mostrado acima, lê-o primeiro com `read_file`.\n"
        "- Faz apenas o que a tua tarefa pede; mantém os ficheiros pequenos e focados.\n"
        f"- Se precisares de avisar um colega ({colleagues}), usa `send_message`.\n"
        "- No fim chama `submit_result` com um resumo curto do que fizeste."
    )
    built.text = "\n\n".join(parts)
    return built
