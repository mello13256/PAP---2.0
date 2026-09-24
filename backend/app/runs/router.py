from __future__ import annotations

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser, SessionDep
from app.events.sse import event_stream
from app.projects.dependencies import OwnedProject
from app.runs import service
from app.runs.dependencies import OwnedRun
from app.runs.schemas import RunCreate, RunOut

router = APIRouter(tags=["runs"])


@router.post(
    "/projects/{project_id}/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED
)
async def create_run(
    data: RunCreate,
    project: OwnedProject,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
) -> RunOut:
    run = await service.create_run(session, request.app.state.bus, project, user, data)
    return RunOut.model_validate(run)


@router.get("/projects/{project_id}/runs", response_model=list[RunOut])
async def list_runs(project: OwnedProject, session: SessionDep) -> list[RunOut]:
    return [RunOut.model_validate(r) for r in await service.list_runs(session, project)]


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(run: OwnedRun) -> RunOut:
    return RunOut.model_validate(run)


@router.get("/runs/{run_id}/events")
async def run_events(
    run: OwnedRun,
    request: Request,
    follow: bool = True,
    after: int = 0,
    last_event_id: int | None = Header(default=None),
) -> StreamingResponse:
    """Eventos do run em tempo real (SSE).

    - ``follow=false``: devolve só os eventos guardados e termina (replay).
    - ``Last-Event-ID`` (enviado pelo browser ao voltar a ligar) ou ``after``:
      só envia eventos posteriores a esse id.
    """
    stream = event_stream(
        request.app.state.bus,
        request.app.state.db.sessionmaker,
        run.id,
        last_event_id=last_event_id if last_event_id is not None else after,
        follow=follow,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
