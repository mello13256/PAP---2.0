from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        secret_key="test-secret-key-not-for-production",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        workspaces_dir=tmp_path / "workspaces",
        auto_migrate=False,
    )


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    # Nos testes as tabelas são criadas diretamente a partir dos modelos (mais rápido);
    # tests/unit/test_migrations.py garante que as migrações produzem o mesmo esquema.
    async with application.state.db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def make_client(app: FastAPI) -> AsyncIterator[Callable[[], Awaitable[AsyncClient]]]:
    """Cria clientes HTTP independentes (cada um com os seus cookies = um "browser")."""
    clients: list[AsyncClient] = []

    async def factory() -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(c)
        return c

    yield factory
    for c in clients:
        await c.aclose()


@pytest.fixture
async def client(make_client) -> AsyncClient:
    return await make_client()


async def register(client: AsyncClient, email: str = "ana@example.com") -> dict:
    response = await client.post(
        "/api/auth/register",
        json={"email": email, "display_name": "Ana", "password": "password-segura"},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    await register(client)
    return client


def use_providers(app: FastAPI, **providers) -> None:
    """Substitui os providers da app (ex.: um FakeProvider a fazer de "ollama")."""
    from app.agents.factory import RuntimeFactory
    from app.agents.runtime import RetryPolicy
    from app.providers.registry import ProviderRegistry

    registry = ProviderRegistry()
    for key, provider in providers.items():
        registry.register(key, provider)
    app.state.providers = registry
    app.state.runtime_factory = RuntimeFactory(
        registry,
        app.state.call_recorder,
        app.state.pricing,
        RetryPolicy(max_attempts=1),
    )
    app.state.run_manager.factory = app.state.runtime_factory
