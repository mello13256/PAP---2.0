import logging

from fastapi import APIRouter, Request
from sqlalchemy import text

from app import __version__

router = APIRouter(tags=["system"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health(request: Request) -> dict:
    settings = request.app.state.settings
    try:
        async with request.app.state.db.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - o health check nunca deve rebentar
        logger.exception("Base de dados indisponível")
        database = "error"
    return {
        "status": "ok" if database == "ok" else "degraded",
        "app": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
        "database": database,
    }
