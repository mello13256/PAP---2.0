"""Workspace partilhado de um projeto: ficheiros com versões.

Regras principais (ver análise, secção 12.1):

- Escrever NUNCA sobrescreve: cria sempre uma nova versão imutável, ligada ao
  agente/utilizador, à tarefa e ao run que a criaram.
- Bloqueio otimista: quem escreve indica a versão em que se baseou. Se entretanto
  outra pessoa/agente criou uma versão mais recente, a escrita é recusada
  (``WorkspaceConflictError``) e é preciso ler a versão atual primeiro. Assim
  ninguém apaga o trabalho de outro sem dar por isso.
- Conteúdo igual ao atual não cria versão nova (evita "correções" vazias).
- A BD é a fonte de verdade; a pasta ``workspaces/<projeto>/`` é um espelho.
"""

from __future__ import annotations

import difflib
import hashlib
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.workspace.models import Artifact, ArtifactVersion, ChangeKind
from app.workspace.paths import (
    MAX_FILE_BYTES,
    MAX_FILES_PER_PROJECT,
    InvalidPathError,
    normalize_path,
)

logger = logging.getLogger(__name__)


class WorkspaceConflictError(AppError):
    status_code = 409
    code = "workspace_conflict"


class WorkspaceLimitError(AppError):
    status_code = 400
    code = "workspace_limit"


@dataclass(frozen=True)
class Author:
    agent_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None


@dataclass(frozen=True)
class WriteResult:
    artifact: Artifact
    version: ArtifactVersion | None  # None = conteúdo igual, sem versão nova
    created: bool

    @property
    def changed(self) -> bool:
        return self.version is not None


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def get_artifact(session: AsyncSession, project_id: uuid.UUID, path: str) -> Artifact | None:
    return await session.scalar(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.path == normalize_path(path),
            Artifact.deleted_at.is_(None),
        )
    )


async def write_file(
    session: AsyncSession,
    project_id: uuid.UUID,
    path: str,
    content: str,
    *,
    author: Author,
    base_version: int | None,
    summary: str = "",
    is_revision: bool = False,
    mirror_root: Path | None = None,
) -> WriteResult:
    """Cria uma nova versão de um ficheiro.

    ``base_version``: a versão que o autor leu antes de escrever (None = acha que
    o ficheiro é novo). Se não corresponder à versão atual → conflito.
    """
    path = normalize_path(path)
    size = len(content.encode("utf-8"))
    if size > MAX_FILE_BYTES:
        raise WorkspaceLimitError(
            f"Ficheiro demasiado grande ({size} bytes; máx. {MAX_FILE_BYTES})"
        )

    artifact = await get_artifact(session, project_id, path)
    created = artifact is None
    if artifact is None:
        count = await session.scalar(
            select(func.count()).select_from(Artifact).where(Artifact.project_id == project_id)
        )
        if (count or 0) >= MAX_FILES_PER_PROJECT:
            raise WorkspaceLimitError(f"Limite de {MAX_FILES_PER_PROJECT} ficheiros atingido")
        artifact = Artifact(
            project_id=project_id,
            path=path,
            current_version=0,
            created_by_agent_id=author.agent_id,
            created_by_user_id=author.user_id,
        )
        session.add(artifact)
        await session.flush()
    elif base_version != artifact.current_version:
        seen = "sem o ter lido" if base_version is None else f"a partir da versão {base_version}"
        raise WorkspaceConflictError(
            f"O ficheiro {path} já está na versão {artifact.current_version} e tentaste "
            f"alterá-lo {seen}. Lê a versão atual (read_file) e integra as alterações."
        )

    current = (
        await _version(session, artifact.id, artifact.current_version) if not created else None
    )
    digest = content_hash(content)
    if current is not None and current.content_hash == digest:
        return WriteResult(artifact, None, created=False)

    kind = (
        ChangeKind.CREATE
        if created
        else (ChangeKind.REVISION if is_revision else ChangeKind.MODIFY)
    )
    version = ArtifactVersion(
        artifact_id=artifact.id,
        version_number=artifact.current_version + 1,
        parent_version_id=current.id if current else None,
        content=content,
        content_hash=digest,
        size_bytes=size,
        author_agent_id=author.agent_id,
        author_user_id=author.user_id,
        run_id=author.run_id,
        task_id=author.task_id,
        change_kind=kind,
        change_summary=summary[:2000],
    )
    session.add(version)
    artifact.current_version = version.version_number
    await session.commit()

    if mirror_root is not None:
        _mirror(mirror_root, project_id, path, content)
    return WriteResult(artifact, version, created=created)


def _mirror(root: Path, project_id: uuid.UUID, path: str, content: str) -> None:
    """Cópia em disco (para abrir no VS Code / exportar). Falhar aqui não é grave."""
    try:
        base = (root / str(project_id)).resolve()
        target = (base / path).resolve()
        if not target.is_relative_to(base):  # defesa extra contra path traversal
            raise InvalidPathError(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except (OSError, InvalidPathError):
        logger.exception("Não foi possível espelhar %s em disco", path)


async def _version(
    session: AsyncSession, artifact_id: uuid.UUID, number: int
) -> ArtifactVersion | None:
    return await session.scalar(
        select(ArtifactVersion).where(
            ArtifactVersion.artifact_id == artifact_id,
            ArtifactVersion.version_number == number,
        )
    )


async def read_file(
    session: AsyncSession, project_id: uuid.UUID, path: str, version: int | None = None
) -> tuple[Artifact, ArtifactVersion]:
    artifact = await get_artifact(session, project_id, path)
    if artifact is None or artifact.current_version == 0:
        raise NotFoundError(f"Ficheiro não encontrado: {normalize_path(path)}")
    found = await _version(session, artifact.id, version or artifact.current_version)
    if found is None:
        raise NotFoundError(f"Versão {version} de {artifact.path} não existe")
    return artifact, found


async def list_files(
    session: AsyncSession, project_id: uuid.UUID
) -> list[tuple[Artifact, ArtifactVersion]]:
    rows = await session.execute(
        select(Artifact, ArtifactVersion)
        .join(
            ArtifactVersion,
            (ArtifactVersion.artifact_id == Artifact.id)
            & (ArtifactVersion.version_number == Artifact.current_version),
        )
        .where(Artifact.project_id == project_id, Artifact.deleted_at.is_(None))
        .order_by(Artifact.path)
    )
    return [(a, v) for a, v in rows.all()]


async def history(session: AsyncSession, project_id: uuid.UUID, path: str) -> list[ArtifactVersion]:
    artifact = await get_artifact(session, project_id, path)
    if artifact is None:
        raise NotFoundError(f"Ficheiro não encontrado: {normalize_path(path)}")
    result = await session.scalars(
        select(ArtifactVersion)
        .where(ArtifactVersion.artifact_id == artifact.id)
        .order_by(ArtifactVersion.version_number)
    )
    return list(result)


def unified_diff(old: str, new: str, path: str, old_label: str, new_label: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"{path} ({old_label})",
            tofile=f"{path} ({new_label})",
        )
    )


async def diff(
    session: AsyncSession, project_id: uuid.UUID, path: str, from_version: int, to_version: int
) -> str:
    """Diff unificado entre duas versões (from_version=0 compara com ficheiro vazio)."""
    old = ""
    if from_version > 0:
        _, old_version = await read_file(session, project_id, path, from_version)
        old = old_version.content
    _, new_version = await read_file(session, project_id, path, to_version)
    return unified_diff(
        old, new_version.content, normalize_path(path), f"v{from_version}", f"v{to_version}"
    )
