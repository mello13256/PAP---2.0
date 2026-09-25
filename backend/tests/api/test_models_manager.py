import json

import httpx
import pytest

from app.models_manager.service import InvalidModelNameError, OllamaManager, native_base_url


def _fake_ollama(pull_lines: list[dict] | None = None, running: bool = True):
    deleted = []

    def handler(request: httpx.Request) -> httpx.Response:
        if not running:
            raise httpx.ConnectError("recusada")
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.34.4"})
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "qwen3:8b",
                            "size": 5_200_000_000,
                            "modified_at": "2026-09-24T00:00:00Z",
                            "details": {
                                "parameter_size": "8.2B",
                                "quantization_level": "Q4_K_M",
                                "family": "qwen3",
                            },
                        }
                    ]
                },
            )
        if request.url.path == "/api/pull":
            body = "\n".join(json.dumps(line) for line in (pull_lines or []))
            return httpx.Response(200, content=body.encode())
        if request.url.path == "/api/delete":
            deleted.append(json.loads(request.content)["model"])
            return httpx.Response(200)
        return httpx.Response(404)

    return httpx.MockTransport(handler), deleted


def test_native_base_url() -> None:
    assert native_base_url("http://127.0.0.1:11434/v1") == "http://127.0.0.1:11434"
    assert native_base_url("http://127.0.0.1:11434/v1/") == "http://127.0.0.1:11434"


async def test_pull_progress_is_aggregated_over_layers() -> None:
    lines = [
        {"status": "pulling manifest"},
        {"status": "pulling a", "digest": "a", "total": 100, "completed": 50},
        {"status": "pulling b", "digest": "b", "total": 300, "completed": 0},
        {"status": "pulling a", "digest": "a", "total": 100, "completed": 100},
        {"status": "pulling b", "digest": "b", "total": 300, "completed": 300},
        {"status": "success"},
    ]
    transport, _ = _fake_ollama(lines)
    manager = OllamaManager("http://ollama.test/v1", transport=transport)
    state, is_new = manager.start_pull("granite3.3:8b")
    assert is_new
    await manager.run_pull(state)
    assert state.done and state.error is None
    assert state.percent == 100.0 and state.total == 400
    # Um segundo pedido enquanto decorre não inicia outro download.
    again, is_new = manager.start_pull("granite3.3:8b")
    assert is_new  # o anterior já terminou


async def test_pull_error_from_ollama() -> None:
    transport, _ = _fake_ollama([{"error": "pull model manifest: file does not exist"}])
    manager = OllamaManager("http://ollama.test/v1", transport=transport)
    state, _ = manager.start_pull("nao-existe:1b")
    await manager.run_pull(state)
    assert state.done and "does not exist" in state.error


async def test_ollama_not_running() -> None:
    transport, _ = _fake_ollama(running=False)
    manager = OllamaManager("http://ollama.test/v1", transport=transport)
    assert await manager.version() is None
    state, _ = manager.start_pull("qwen3:8b")
    await manager.run_pull(state)
    assert "não está a correr" in state.error


def test_model_names_are_validated() -> None:
    manager = OllamaManager("http://x/v1")
    for bad in ["", "../etc", "rm -rf /", "a" * 200]:
        with pytest.raises(InvalidModelNameError):
            manager.start_pull(bad)


async def test_models_api(app, auth_client) -> None:
    transport, deleted = _fake_ollama([{"status": "success"}])
    app.state.ollama = OllamaManager("http://ollama.test/v1", transport=transport)

    status = (await auth_client.get("/api/models/status")).json()
    assert status["ollama"]["running"] is True
    assert status["installed"][0]["name"] == "qwen3:8b"
    assert status["installed"][0]["parameter_size"] == "8.2B"

    catalog = (await auth_client.get("/api/models/catalog")).json()
    assert any(m["name"] == "granite3.3:8b" and m["recommended"] for m in catalog)

    started = await auth_client.post("/api/models/pull", json={"name": "granite3.3:8b"})
    assert started.status_code == 202
    await app.state.background.wait_all()
    [pull] = (await auth_client.get("/api/models/pulls")).json()
    assert pull["done"] and pull["error"] is None

    assert (await auth_client.delete("/api/models/qwen3:8b")).status_code == 204
    assert deleted == ["qwen3:8b"]

    assert (await auth_client.post("/api/models/pull", json={"name": "../x"})).status_code == 400
