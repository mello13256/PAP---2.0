from __future__ import annotations

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser, SessionDep
from app.events.sse import event_stream
from app.metrics.service import compute_run_metrics
from app.orchestration.strategies import STRATEGIES
from app.projects.dependencies import OwnedProject
from app.reviews import service as reviews_service
from app.reviews.schemas import ReviewOut
from app.runs import service
from app.runs.dependencies import OwnedRun
from app.runs.schemas import RecentRunOut, RunCreate, RunOut, StrategyOut

router = APIRouter(tags=["runs"])


@router.get("/strategies", response_model=list[StrategyOut])
async def list_strategies() -> list[StrategyOut]:
    return [
        StrategyOut(key=s.key, name=s.name, description=s.description, min_agents=s.min_agents)
        for s in STRATEGIES.values()
    ]


@router.get("/runs/recent", response_model=list[RecentRunOut])
async def recent_runs(user: CurrentUser, session: SessionDep) -> list[RecentRunOut]:
    return [
        RecentRunOut(**RunOut.model_validate(run).model_dump(), project_name=name)
        for run, name in await service.recent_runs(session, user)
    ]


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
    """Cria um run e (por defeito) inicia logo o MultiMind."""
    run = await service.create_run(session, request.app.state.bus, project, user, data)
    if data.autostart:
        await request.app.state.run_manager.start(run.id)
    return RunOut.model_validate(run)


@router.get("/projects/{project_id}/runs", response_model=list[RunOut])
async def list_runs(project: OwnedProject, session: SessionDep) -> list[RunOut]:
    return [RunOut.model_validate(r) for r in await service.list_runs(session, project)]


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(run: OwnedRun, session: SessionDep) -> RunOut:
    await session.refresh(run)
    return RunOut.model_validate(run)


async def _reload(session: SessionDep, run) -> RunOut:
    await session.refresh(run)
    return RunOut.model_validate(run)


@router.post("/runs/{run_id}/start", response_model=RunOut)
async def start_run(run: OwnedRun, session: SessionDep, request: Request) -> RunOut:
    await request.app.state.run_manager.start(run.id)
    return await _reload(session, run)


@router.post("/runs/{run_id}/pause", response_model=RunOut)
async def pause_run(run: OwnedRun, session: SessionDep, request: Request) -> RunOut:
    """Pausa cooperativa: a chamada em curso termina e o run pára antes do passo seguinte."""
    await request.app.state.run_manager.pause(run.id)
    return await _reload(session, run)


@router.post("/runs/{run_id}/resume", response_model=RunOut)
async def resume_run(run: OwnedRun, session: SessionDep, request: Request) -> RunOut:
    await request.app.state.run_manager.resume(run.id)
    return await _reload(session, run)


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
async def cancel_run(run: OwnedRun, session: SessionDep, request: Request) -> RunOut:
    await request.app.state.run_manager.cancel(run.id)
    return await _reload(session, run)


@router.get("/runs/{run_id}/reviews", response_model=list[ReviewOut])
async def list_reviews(run: OwnedRun, session: SessionDep) -> list[ReviewOut]:
    return await reviews_service.list_reviews(session, run.id)


@router.get("/runs/{run_id}/metrics")
async def run_metrics(run: OwnedRun, session: SessionDep) -> dict:
    metrics = await compute_run_metrics(session, run.id)
    return {
        column.name: getattr(metrics, column.name)
        for column in metrics.__table__.columns
        if column.name != "run_id"
    }


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
