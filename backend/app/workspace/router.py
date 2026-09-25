from __future__ import annotations

import io
import re
import zipfile

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser, SessionDep
from app.projects.dependencies import OwnedProject
from app.workspace import service
from app.workspace.models import Artifact, ArtifactVersion
from app.workspace.schemas import DiffOut, FileContent, FileEntry, FileWrite, VersionOut

router = APIRouter(prefix="/projects/{project_id}/files", tags=["workspace"])


def _version_out(artifact: Artifact, v: ArtifactVersion) -> dict:
    return {
        "path": artifact.path,
        "version": v.version_number,
        "size_bytes": v.size_bytes,
        "change_kind": v.change_kind,
        "change_summary": v.change_summary,
        "author_agent_id": v.author_agent_id,
        "author_user_id": v.author_user_id,
        "run_id": v.run_id,
        "task_id": v.task_id,
        "created_at": v.created_at,
    }


@router.get("", response_model=list[FileEntry])
async def list_files(project: OwnedProject, session: SessionDep) -> list[FileEntry]:
    return [
        FileEntry(
            path=a.path,
            version=v.version_number,
            size_bytes=v.size_bytes,
            change_kind=v.change_kind,
            author_agent_id=v.author_agent_id,
            author_user_id=v.author_user_id,
            updated_at=v.created_at,
        )
        for a, v in await service.list_files(session, project.id)
    ]


@router.get("/content", response_model=FileContent)
async def read_file(
    project: OwnedProject, session: SessionDep, path: str, version: int | None = Query(None, ge=1)
) -> FileContent:
    artifact, v = await service.read_file(session, project.id, path, version)
    return FileContent(
        **_version_out(artifact, v), content=v.content, current_version=artifact.current_version
    )


@router.get("/history", response_model=list[VersionOut])
async def file_history(project: OwnedProject, session: SessionDep, path: str) -> list[VersionOut]:
    artifact = await service.get_artifact(session, project.id, path)
    versions = await service.history(session, project.id, path)
    return [VersionOut(**_version_out(artifact, v)) for v in versions]


@router.get("/diff", response_model=DiffOut)
async def file_diff(
    project: OwnedProject,
    session: SessionDep,
    path: str,
    from_version: int = Query(ge=0),
    to_version: int = Query(ge=1),
) -> DiffOut:
    text = await service.diff(session, project.id, path, from_version, to_version)
    return DiffOut(path=path, from_version=from_version, to_version=to_version, diff=text)


@router.put("", response_model=VersionOut)
async def write_file(
    data: FileWrite, project: OwnedProject, user: CurrentUser, session: SessionDep, request: Request
) -> VersionOut:
    """O utilizador também pode editar ficheiros (com as mesmas regras de conflito)."""
    result = await service.write_file(
        session,
        project.id,
        data.path,
        data.content,
        author=service.Author(user_id=user.id),
        base_version=data.base_version,
        summary=data.summary or "Editado pelo utilizador",
        mirror_root=request.app.state.settings.workspaces_dir,
    )
    _, v = await service.read_file(session, project.id, result.artifact.path)
    return VersionOut(**_version_out(result.artifact, v))


@router.get("/export")
async def export_zip(project: OwnedProject, session: SessionDep) -> StreamingResponse:
    """Descarrega a versão atual de todos os ficheiros num ZIP."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for artifact, v in await service.list_files(session, project.id):
            archive.writestr(artifact.path, v.content)
    buffer.seek(0)
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", project.name)[:40] or "projeto"
    filename = f"multimind-{safe_name}.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
