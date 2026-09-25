from sqlalchemy import select

from app.metrics.models import CallPurpose, LLMCall
from app.providers.base import ProviderError, ProviderErrorKind
from app.providers.fake_provider import FakeProvider, FakeResponse
from tests.conftest import register, use_providers


async def test_new_users_get_the_default_agents(auth_client) -> None:
    agents = (await auth_client.get("/api/agents")).json()
    assert [a["name"] for a in agents] == ["Granite", "Qwen", "Simulado"]
    granite = agents[0]
    assert granite["provider"] == "ollama"
    assert granite["model"] == "granite3.3:8b"
    assert "planning" in granite["capabilities"]
    assert agents[2]["enabled"] is False  # o simulado vem desativado

    # Pedir os pré-definidos outra vez não cria duplicados.
    assert (await auth_client.post("/api/agents/defaults")).json() == []
    assert len((await auth_client.get("/api/agents")).json()) == 3


async def test_create_update_and_disable_agent(auth_client) -> None:
    created = await auth_client.post(
        "/api/agents",
        json={
            "name": "Revisor",
            "provider": "fake",
            "model": "fake-model",
            "capabilities": ["review"],
            "config": {"temperature": 0.1, "max_output_tokens": 1000},
        },
    )
    assert created.status_code == 201, created.text
    agent = created.json()
    assert agent["provider_available"] is True

    updated = await auth_client.patch(
        f"/api/agents/{agent['id']}", json={"model": "outro-modelo", "capabilities": ["testing"]}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["model"] == "outro-modelo"
    assert updated.json()["capabilities"] == ["testing"]
    assert updated.json()["config"]["temperature"] == 0.1  # não foi apagado

    # Nunca foi usado → é apagado.
    removed = await auth_client.delete(f"/api/agents/{agent['id']}")
    assert removed.json() == {"deleted": True, "agent": None}
    assert (await auth_client.get(f"/api/agents/{agent['id']}")).status_code == 404


async def test_used_agents_are_only_disabled(app, auth_client) -> None:
    use_providers(app, ollama=FakeProvider([FakeResponse(text="olá")]))
    granite = (await auth_client.get("/api/agents")).json()[0]
    await auth_client.post(f"/api/agents/{granite['id']}/ping")  # fica nas métricas

    removed = (await auth_client.delete(f"/api/agents/{granite['id']}")).json()
    assert removed["deleted"] is False
    assert removed["agent"]["enabled"] is False


async def test_agent_validation(auth_client) -> None:
    unknown = await auth_client.post(
        "/api/agents", json={"name": "X", "provider": "gemini", "model": "m"}
    )
    assert unknown.status_code == 400
    assert unknown.json()["error"]["code"] == "unknown_provider"

    bad_capability = await auth_client.post(
        "/api/agents",
        json={"name": "X", "provider": "fake", "model": "m", "capabilities": ["voar"]},
    )
    assert bad_capability.status_code == 422

    bad_config = await auth_client.post(
        "/api/agents",
        json={"name": "X", "provider": "fake", "model": "m", "config": {"temperature": 9}},
    )
    assert bad_config.status_code == 422


async def test_agents_are_private(make_client) -> None:
    alice = await make_client()
    await register(alice, "alice@example.com")
    agent_id = (await alice.get("/api/agents")).json()[0]["id"]

    bob = await make_client()
    await register(bob, "bob@example.com")
    assert (await bob.get(f"/api/agents/{agent_id}")).status_code == 404
    assert (await bob.patch(f"/api/agents/{agent_id}", json={"name": "x"})).status_code == 404


async def test_ping_calls_the_model_and_records_metrics(app, auth_client) -> None:
    use_providers(app, ollama=FakeProvider([FakeResponse(text="Sou o Granite.")]))
    granite = (await auth_client.get("/api/agents")).json()[0]

    result = (await auth_client.post(f"/api/agents/{granite['id']}/ping")).json()
    assert result["ok"] is True
    assert result["text"] == "Sou o Granite."
    assert result["output_tokens"] == 3

    async with app.state.db.sessionmaker() as session:
        [call] = list(await session.scalars(select(LLMCall)))
    assert call.purpose is CallPurpose.PING
    assert str(call.agent_id) == granite["id"]


async def test_ping_reports_errors_without_crashing(app, auth_client) -> None:
    down = ProviderError(ProviderErrorKind.UNAVAILABLE, "Ollama desligado")
    use_providers(app, ollama=FakeProvider([FakeResponse(error=down)]))
    granite = (await auth_client.get("/api/agents")).json()[0]

    result = (await auth_client.post(f"/api/agents/{granite['id']}/ping")).json()
    assert result["ok"] is False
    assert result["error_kind"] == "unavailable"


async def test_providers_endpoint(auth_client) -> None:
    keys = [p["key"] for p in (await auth_client.get("/api/providers")).json()]
    assert "fake" in keys
