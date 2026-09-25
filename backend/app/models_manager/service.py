"""Gestão dos modelos locais através da API nativa do Ollama.

O MultiMind fala com os modelos pela API compatível com a OpenAI (``/v1``), mas
para listar, descarregar e remover modelos usa a API própria do Ollama (``/api``):

    GET    /api/version   o Ollama está a correr?
    GET    /api/tags      modelos instalados
    POST   /api/pull      descarregar (progresso em linhas JSON, em streaming)
    DELETE /api/delete    remover
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from app.core.errors import AppError

logger = logging.getLogger(__name__)

MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/:]{0,120}$")


class OllamaUnavailableError(AppError):
    status_code = 503
    code = "ollama_unavailable"


class InvalidModelNameError(AppError):
    status_code = 400
    code = "invalid_model_name"


def native_base_url(openai_base_url: str) -> str:
    """http://127.0.0.1:11434/v1 → http://127.0.0.1:11434"""
    url = openai_base_url.rstrip("/")
    return url[: -len("/v1")] if url.endswith("/v1") else url


def validate_name(name: str) -> str:
    name = name.strip()
    if not MODEL_NAME.match(name):
        raise InvalidModelNameError(f"Nome de modelo inválido: {name!r}")
    return name


@dataclass
class PullState:
    name: str
    status: str = "a iniciar"
    completed: int = 0
    total: int = 0
    done: bool = False
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    layers: dict[str, tuple[int, int]] = field(default_factory=dict, repr=False)

    @property
    def percent(self) -> float:
        return round(100 * self.completed / self.total, 1) if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("layers")
        data["percent"] = self.percent
        return data


class OllamaManager:
    def __init__(self, base_url: str, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = native_base_url(base_url)
        self._transport = transport
        self.pulls: dict[str, PullState] = {}

    def _client(self, timeout: float | None = 10.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=self._transport)

    async def version(self) -> str | None:
        try:
            async with self._client(timeout=3.0) as client:
                response = await client.get("/api/version")
                response.raise_for_status()
                return response.json().get("version", "?")
        except (httpx.HTTPError, ValueError):
            return None

    async def installed(self) -> list[dict[str, Any]]:
        try:
            async with self._client() as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError(
                "O Ollama não está a correr. Abre a aplicação Ollama e tenta outra vez."
            ) from exc
        models = []
        for m in response.json().get("models", []):
            details = m.get("details") or {}
            models.append(
                {
                    "name": m.get("name") or m.get("model"),
                    "size_bytes": m.get("size", 0),
                    "modified_at": m.get("modified_at"),
                    "parameter_size": details.get("parameter_size"),
                    "quantization": details.get("quantization_level"),
                    "family": details.get("family"),
                }
            )
        return sorted(models, key=lambda x: x["name"] or "")

    async def delete(self, name: str) -> None:
        name = validate_name(name)
        try:
            async with self._client() as client:
                response = await client.request("DELETE", "/api/delete", json={"model": name})
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError("O Ollama não está a correr.") from exc
        if response.status_code == 404:
            raise InvalidModelNameError(f"O modelo {name} não está instalado")
        response.raise_for_status()

    def start_pull(self, name: str) -> tuple[PullState, bool]:
        """Regista o download. Devolve (estado, é_novo)."""
        name = validate_name(name)
        current = self.pulls.get(name)
        if current is not None and not current.done:
            return current, False
        state = PullState(name)
        self.pulls[name] = state
        return state, True

    async def run_pull(self, state: PullState) -> None:
        """Descarrega o modelo, atualizando ``state`` com o progresso."""
        try:
            async with (
                self._client(timeout=None) as client,
                client.stream(
                    "POST", "/api/pull", json={"model": state.name, "stream": True}
                ) as response,
            ):
                if response.status_code >= 400:
                    body = (await response.aread()).decode(errors="replace")
                    raise RuntimeError(body[:300] or f"HTTP {response.status_code}")
                async for line in response.aiter_lines():
                    if line.strip():
                        self._apply(state, json.loads(line))
            if state.error is None:
                state.status = "concluído"
                state.completed = state.total or state.completed
        except httpx.HTTPError:
            state.error = "O Ollama não está a correr (ou a ligação caiu)."
        except asyncio.CancelledError:
            state.error = "Cancelado"
            raise
        except Exception as exc:  # noqa: BLE001 - o erro fica visível na interface
            state.error = str(exc)
        finally:
            state.done = True

    @staticmethod
    def _apply(state: PullState, data: dict[str, Any]) -> None:
        if "error" in data:
            state.error = str(data["error"])
            return
        state.status = data.get("status", state.status)
        digest = data.get("digest")
        if digest and data.get("total"):
            state.layers[digest] = (int(data.get("completed", 0)), int(data["total"]))
            state.completed = sum(c for c, _ in state.layers.values())
            state.total = sum(t for _, t in state.layers.values())
