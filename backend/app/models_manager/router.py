from __future__ import annotations

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser
from app.models_manager.catalog import CATALOG
from app.models_manager.service import OllamaManager, validate_name

router = APIRouter(prefix="/models", tags=["models"])


class PullRequest(BaseModel):
    name: str = Field(min_length=1, max_length=121)


def _manager(request: Request) -> OllamaManager:
    return request.app.state.ollama


@router.get("/status")
async def model_status(request: Request, _: CurrentUser) -> dict:
    """O Ollama está a correr? Que modelos estão instalados?"""
    manager = _manager(request)
    version = await manager.version()
    installed = await manager.installed() if version else []
    return {
        "ollama": {"running": version is not None, "version": version, "url": manager.base_url},
        "installed": installed,
    }


@router.get("/catalog")
async def model_catalog(_: CurrentUser) -> list[dict]:
    return CATALOG


@router.get("/pulls")
async def list_pulls(request: Request, _: CurrentUser) -> list[dict]:
    return [p.to_dict() for p in _manager(request).pulls.values()]


@router.post("/pull", status_code=status.HTTP_202_ACCEPTED)
async def pull_model(data: PullRequest, request: Request, _: CurrentUser) -> dict:
    """Começa a descarregar um modelo (continua em segundo plano; ver /models/pulls)."""
    manager = _manager(request)
    state, is_new = manager.start_pull(data.name)
    if is_new:
        request.app.state.background.spawn(manager.run_pull(state), name=f"pull:{state.name}")
    return state.to_dict()


@router.delete("/{name:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(name: str, request: Request, _: CurrentUser) -> None:
    await _manager(request).delete(validate_name(name))
