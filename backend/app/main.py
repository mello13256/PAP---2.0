"""Ponto de entrada do backend.

``create_app`` constrói a aplicação a partir de um objeto ``Settings``; os testes
usam-no para criar aplicações isoladas (com a sua própria base de dados).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.agents import router as agents_router
from app.agents.factory import RuntimeFactory
from app.agents.service import remove_duplicate_agents
from app.api import health
from app.auth import router as auth_router
from app.core.background import BackgroundTasks
from app.core.config import BACKEND_DIR, Settings, get_settings
from app.core.errors import NotFoundError, register_error_handlers
from app.core.logging import configure_logging
from app.db.migrations import upgrade_to_head
from app.db.session import Database
from app.events.bus import EventBus
from app.messages import router as messages_router
from app.metrics.recorder import DatabaseCallRecorder
from app.orchestration.run_manager import RunManager
from app.projects import router as projects_router
from app.providers.pricing import PricingTable
from app.providers.setup import build_registry
from app.runs import router as runs_router
from app.tasks import router as tasks_router
from app.workspace import router as workspace_router

logger = logging.getLogger("multimind")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    db = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.secret_key_was_generated:
            logger.warning(
                "SECRET_KEY não definida no .env: a usar a chave local de desenvolvimento."
            )
        if settings.auto_migrate:
            # O Alembic usa o seu próprio event loop, por isso corre numa thread à parte.
            await asyncio.to_thread(upgrade_to_head, settings.database_url)
        await app.state.run_manager.recover_interrupted()
        async with db.sessionmaker() as session:
            removed = await remove_duplicate_agents(session)
        if removed:
            logger.info("Agentes repetidos arrumados: %d", removed)
        logger.info("MultiMind %s a arrancar (%s)", __version__, settings.environment)
        yield
        await app.state.background.cancel_all()
        await db.dispose()
        logger.info("MultiMind a terminar")

    app = FastAPI(
        title="MultiMind API",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
    )
    app.state.settings = settings
    app.state.db = db
    app.state.providers = build_registry(settings)
    app.state.pricing = PricingTable.from_file(BACKEND_DIR / "pricing.json")
    app.state.call_recorder = DatabaseCallRecorder(db.sessionmaker)
    app.state.runtime_factory = RuntimeFactory(
        app.state.providers, app.state.call_recorder, app.state.pricing
    )
    app.state.bus = EventBus(db.sessionmaker)
    app.state.background = BackgroundTasks()
    app.state.run_manager = RunManager(
        db.sessionmaker,
        app.state.bus,
        app.state.runtime_factory,
        app.state.background,
        settings.workspaces_dir,
    )
    register_error_handlers(app)

    app.include_router(health.router, prefix="/api")
    app.include_router(auth_router.router, prefix="/api")
    app.include_router(projects_router.router, prefix="/api")
    app.include_router(agents_router.router, prefix="/api")
    app.include_router(runs_router.router, prefix="/api")
    app.include_router(messages_router.router, prefix="/api")
    app.include_router(tasks_router.router, prefix="/api")
    app.include_router(workspace_router.router, prefix="/api")
    _serve_frontend(app)
    return app


FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"


def _serve_frontend(app: FastAPI) -> None:
    """Serve a interface compilada (frontend/dist) no mesmo endereço da API.

    Assim basta um servidor e um endereço (http://127.0.0.1:8000). Qualquer rota
    que não seja /api devolve o index.html (a navegação é feita pelo React).
    """
    index = FRONTEND_DIST / "index.html"
    if not index.exists():
        return
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise NotFoundError("Endpoint não encontrado")
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
