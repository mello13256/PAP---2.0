"""Ponto de entrada do backend.

``create_app`` constrói a aplicação a partir de um objeto ``Settings``; os testes
usam-no para criar aplicações isoladas (com a sua própria base de dados).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api import health
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging

logger = logging.getLogger("multimind")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.secret_key_was_generated:
            logger.warning("SECRET_KEY não definida: a usar uma chave temporária.")
        logger.info("MultiMind %s a arrancar (%s)", __version__, settings.environment)
        yield
        logger.info("MultiMind a terminar")

    app = FastAPI(
        title="MultiMind API",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
    )
    app.state.settings = settings
    register_error_handlers(app)

    app.include_router(health.router, prefix="/api")
    return app


app = create_app()
