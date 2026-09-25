"""Ferramentas que os agentes podem usar.

Os agentes nunca tocam no disco nem na BD diretamente: pedem uma ferramenta e o
sistema valida os argumentos, aplica as regras (caminhos seguros, versões,
conflitos, limites) e devolve o resultado. Não há ferramentas de execução de
código, rede ou shell (ver análise, secção 14).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.agents.models import Agent
from app.core.errors import AppError
from app.messages.models import MessageKind
from app.orchestration.context import RunContext
from app.providers.base import ToolSpec
from app.reviews.models import Severity, Verdict
from app.tasks.schemas import PlannedTask
from app.workspace import service as workspace


class ToolError(Exception):
    """Erro devolvido ao agente como resultado da ferramenta (ele pode corrigir)."""


def _schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema


def parse_args(model: type[BaseModel], arguments: dict[str, Any]) -> Any:
    try:
        return model.model_validate(arguments)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'argumentos'}: {e['msg']}"
            for e in exc.errors()
        )
        raise ToolError(f"Argumentos inválidos: {problems}") from None


# ------------------------------------------------------------------ argumentos


class ReadFileArgs(BaseModel):
    path: str = Field(description="Caminho relativo do ficheiro, ex.: src/app.py")


class WriteFileArgs(BaseModel):
    path: str = Field(description="Caminho relativo do ficheiro, ex.: src/app.py")
    content: str = Field(description="Conteúdo COMPLETO do ficheiro (não um excerto nem um diff)")
    summary: str = Field(default="", description="Uma frase a explicar a alteração")


class SendMessageArgs(BaseModel):
    to: str = Field(description="Nome do agente destinatário")
    content: str = Field(description="A mensagem")


class SubmitResultArgs(BaseModel):
    summary: str = Field(min_length=1, description="Resumo do que foi feito nesta tarefa")


class SubmitPlanArgs(BaseModel):
    tasks: list[PlannedTask] = Field(min_length=1, description="Lista de tarefas")


class ReviewIssueArgs(BaseModel):
    severity: Severity = Field(description="CRITICAL, MAJOR, MINOR ou INFO")
    description: str = Field(min_length=1)
    file: str | None = Field(default=None, description="Ficheiro em causa, se aplicável")
    suggestion: str = Field(default="", description="Como corrigir")


class SubmitReviewArgs(BaseModel):
    verdict: Verdict = Field(description="APPROVED ou NEEDS_REVISION")
    summary: str = Field(min_length=1, description="Avaliação geral")
    issues: list[ReviewIssueArgs] = Field(default_factory=list)


# ------------------------------------------------------------------ specs

LIST_FILES = ToolSpec(
    "list_files",
    "Lista os ficheiros do projeto (caminho e versão).",
    {"type": "object", "properties": {}},
)
READ_FILE = ToolSpec(
    "read_file", "Lê a versão atual de um ficheiro do projeto.", _schema(ReadFileArgs)
)
WRITE_FILE = ToolSpec(
    "write_file",
    "Cria ou substitui um ficheiro do projeto (cria uma nova versão; nada é perdido).",
    _schema(WriteFileArgs),
)
SEND_MESSAGE = ToolSpec(
    "send_message", "Envia uma mensagem a outro agente da equipa.", _schema(SendMessageArgs)
)
SUBMIT_RESULT = ToolSpec(
    "submit_result",
    "Entrega o resultado da tarefa. Termina o teu trabalho.",
    _schema(SubmitResultArgs),
)
SUBMIT_PLAN = ToolSpec("submit_plan", "Entrega o plano de tarefas.", _schema(SubmitPlanArgs))
SUBMIT_REVIEW = ToolSpec("submit_review", "Entrega a revisão.", _schema(SubmitReviewArgs))


# ------------------------------------------------------------------ execução


@dataclass
class WorkspaceTools:
    """Ferramentas de um agente numa tarefa. Guarda as versões que ele já viu."""

    ctx: RunContext
    agent: Agent
    task_id: uuid.UUID | None
    is_revision: bool = False
    seen_versions: dict[str, int] = field(default_factory=dict)
    changed: dict[str, int] = field(default_factory=dict)  # caminho → versão criada
    messages_sent: int = 0

    def handlers(self) -> dict[str, Any]:
        return {
            "list_files": self.list_files,
            "read_file": self.read_file,
            "write_file": self.write_file,
            "send_message": self.send_message,
        }

    async def list_files(self, _: dict[str, Any]) -> str:
        async with self.ctx.sessionmaker() as session:
            files = await workspace.list_files(session, self.ctx.project_id)
        if not files:
            return "O projeto ainda não tem ficheiros."
        return "\n".join(
            f"{a.path} (versão {v.version_number}, {v.size_bytes} bytes)" for a, v in files
        )

    async def read_file(self, arguments: dict[str, Any]) -> str:
        args = parse_args(ReadFileArgs, arguments)
        try:
            async with self.ctx.sessionmaker() as session:
                artifact, version = await workspace.read_file(
                    session, self.ctx.project_id, args.path
                )
        except AppError as exc:
            raise ToolError(exc.message) from None
        self.seen_versions[artifact.path] = version.version_number
        return f"{artifact.path} (versão {version.version_number}):\n{version.content}"

    async def write_file(self, arguments: dict[str, Any]) -> str:
        args = parse_args(WriteFileArgs, arguments)
        try:
            path = workspace.normalize_path(args.path)
            async with self.ctx.sessionmaker() as session:
                result = await workspace.write_file(
                    session,
                    self.ctx.project_id,
                    path,
                    args.content,
                    author=workspace.Author(
                        agent_id=self.agent.id, run_id=self.ctx.run_id, task_id=self.task_id
                    ),
                    base_version=self.seen_versions.get(path),
                    summary=args.summary,
                    is_revision=self.is_revision,
                    mirror_root=self.ctx.workspaces_dir,
                )
        except AppError as exc:
            raise ToolError(exc.message) from None

        if not result.changed:
            return f"{path}: o conteúdo é igual à versão atual; nada foi alterado."
        version = result.version.version_number
        self.seen_versions[path] = version
        self.changed[path] = version
        await self.ctx.event(
            "file.changed",
            {
                "path": path,
                "version": version,
                "change_kind": result.version.change_kind,
                "agent_id": self.agent.id,
                "agent_name": self.agent.name,
                "task_id": self.task_id,
                "summary": args.summary,
            },
        )
        return f"Guardado {path} (versão {version})."

    async def send_message(self, arguments: dict[str, Any]) -> str:
        args = parse_args(SendMessageArgs, arguments)
        limit = self.ctx.strategy.limits.max_messages_per_task
        if self.messages_sent >= limit:
            raise ToolError(f"Limite de {limit} mensagens por tarefa atingido")
        recipient = next(
            (a for a in self.ctx.participants if a.name.lower() == args.to.strip().lower()), None
        )
        if recipient is None or recipient.id == self.agent.id:
            names = ", ".join(a.name for a in self.ctx.participants if a.id != self.agent.id)
            raise ToolError(f"Destinatário desconhecido. Colegas disponíveis: {names or 'nenhum'}")
        self.messages_sent += 1
        await self.ctx.say(
            MessageKind.AGENT,
            args.content,
            task_id=self.task_id,
            sender_agent_id=self.agent.id,
            recipient_agent_id=recipient.id,
        )
        return f"Mensagem entregue a {recipient.name}. Ele vai vê-la no contexto da próxima tarefa."
