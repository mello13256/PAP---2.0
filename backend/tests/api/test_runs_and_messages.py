from app.providers.fake_provider import FakeProvider, FakeResponse
from tests.conftest import register, use_providers


async def _project(client) -> dict:
    return (await client.post("/api/projects", json={"name": "Loja"})).json()


async def _run(client, project_id: str, objective: str = "Criar uma app de inventário") -> dict:
    response = await client.post(
        f"/api/projects/{project_id}/runs", json={"objective": objective, "autostart": False}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_and_list_runs(auth_client) -> None:
    project = await _project(auth_client)
    run = await _run(auth_client, project["id"])
    assert run["status"] == "PENDING"
    listed = (await auth_client.get(f"/api/projects/{project['id']}/runs")).json()
    assert [r["id"] for r in listed] == [run["id"]]
    assert (await auth_client.get(f"/api/runs/{run['id']}")).json()["objective"] == run["objective"]


async def test_runs_are_private(make_client) -> None:
    alice = await make_client()
    await register(alice, "alice@example.com")
    run = await _run(alice, (await _project(alice))["id"])

    bob = await make_client()
    await register(bob, "bob@example.com")
    for url in (f"/api/runs/{run['id']}", f"/api/runs/{run['id']}/messages"):
        assert (await bob.get(url)).status_code == 404
    assert (await bob.get(f"/api/runs/{run['id']}/events?follow=false")).status_code == 404


async def test_user_message_is_stored_and_becomes_an_event(auth_client) -> None:
    run = await _run(auth_client, (await _project(auth_client))["id"])
    posted = await auth_client.post(
        f"/api/runs/{run['id']}/messages", json={"content": "Usem arquitetura REST."}
    )
    assert posted.status_code == 201
    assert posted.json()["kind"] == "USER"

    messages = (await auth_client.get(f"/api/runs/{run['id']}/messages")).json()
    assert [m["content"] for m in messages] == ["Usem arquitetura REST."]

    replay = await auth_client.get(f"/api/runs/{run['id']}/events?follow=false")
    assert replay.headers["content-type"].startswith("text/event-stream")
    assert "event: run.created" in replay.text
    assert "event: message.created" in replay.text
    assert "Usem arquitetura REST." in replay.text


async def test_agents_talk_through_the_orchestrator(app, auth_client) -> None:
    """Granite responde; depois o Qwen responde vendo o que o Granite disse."""

    def respond(request):
        prompt = request.messages[-1].content
        if "És o agente Granite" in prompt:
            return FakeResponse(text="Analisei a tarefa. Recomendo arquitetura REST.")
        assert "[Granite]: Analisei a tarefa. Recomendo arquitetura REST." in prompt
        return FakeResponse(text="Concordo parcialmente: falta autenticação.")

    use_providers(app, ollama=FakeProvider(respond, chunk_size=5))
    agents = {a["name"]: a for a in (await auth_client.get("/api/agents")).json()}
    run = await _run(auth_client, (await _project(auth_client))["id"])
    bus = app.state.bus

    import uuid

    with bus.subscribe(uuid.UUID(run["id"])) as sub:
        accepted = await auth_client.post(
            f"/api/runs/{run['id']}/ask",
            json={"agent_id": agents["Granite"]["id"], "prompt": "Que arquitetura usar?"},
        )
        assert accepted.status_code == 202
        await app.state.background.wait_all()
        await auth_client.post(
            f"/api/runs/{run['id']}/ask", json={"agent_id": agents["Qwen"]["id"]}
        )
        await app.state.background.wait_all()

        live = []
        while not sub.queue.empty():
            live.append(sub.queue.get_nowait())

    deltas = [e for e in live if e.type == "agent.delta"]
    assert len(deltas) > 2  # a resposta chegou aos bocados (streaming)
    assert all(e.id is None for e in deltas)  # e esses bocados não foram guardados

    messages = (await auth_client.get(f"/api/runs/{run['id']}/messages")).json()
    assert [(m["kind"], m["content"]) for m in messages] == [
        ("USER", "Que arquitetura usar?"),
        ("AGENT", "Analisei a tarefa. Recomendo arquitetura REST."),
        ("AGENT", "Concordo parcialmente: falta autenticação."),
    ]
    assert messages[1]["sender_agent_id"] == agents["Granite"]["id"]
    assert messages[2]["sender_agent_id"] == agents["Qwen"]["id"]
    assert messages[2]["meta"]["output_tokens"] is not None


async def test_agent_failure_becomes_a_system_message(app, auth_client) -> None:
    from app.providers.base import ProviderError, ProviderErrorKind

    down = ProviderError(ProviderErrorKind.UNAVAILABLE, "Ollama desligado")
    use_providers(app, ollama=FakeProvider([FakeResponse(error=down)]))
    granite = (await auth_client.get("/api/agents")).json()[0]
    run = await _run(auth_client, (await _project(auth_client))["id"])

    await auth_client.post(f"/api/runs/{run['id']}/ask", json={"agent_id": granite["id"]})
    await app.state.background.wait_all()

    [message] = (await auth_client.get(f"/api/runs/{run['id']}/messages")).json()
    assert message["kind"] == "SYSTEM"
    assert "Granite" in message["content"]


async def test_disabled_agent_cannot_be_asked(auth_client) -> None:
    simulado = (await auth_client.get("/api/agents")).json()[2]
    run = await _run(auth_client, (await _project(auth_client))["id"])
    response = await auth_client.post(
        f"/api/runs/{run['id']}/ask", json={"agent_id": simulado["id"]}
    )
    assert response.status_code == 409
