"""Runs completos com agentes simulados (sem internet, sem custos)."""

import asyncio
import dataclasses
import uuid

from sqlalchemy import select

from app.orchestration.orchestrator import execute_run
from app.providers.fake_provider import FakeProvider, FakeResponse
from app.runs.models import RunEvent
from tests.conftest import use_providers
from tests.integration.scripted import FIXED, team_script


async def _start(client, project_id: str, **extra) -> dict:
    response = await client.post(
        f"/api/projects/{project_id}/runs", json={"objective": "x", **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _project(client) -> str:
    return (await client.post("/api/projects", json={"name": "Loja"})).json()["id"]


async def _wait_finished(client, run_id: str, app) -> dict:
    await app.state.background.wait_all()
    return (await client.get(f"/api/runs/{run_id}")).json()


async def test_full_run_plan_execute_review_revise_finalize(app, auth_client) -> None:
    use_providers(app, ollama=FakeProvider(team_script))
    project_id = await _project(auth_client)
    created = await auth_client.post(
        f"/api/projects/{project_id}/runs",
        json={"objective": "Criar uma app de inventário", "strategy_key": "collaborative"},
    )
    assert created.status_code == 201, created.text
    run = await _wait_finished(auth_client, created.json()["id"], app)
    run_id = run["id"]

    assert run["status"] == "COMPLETED", run
    assert run["final_result"] == "Relatório: app criada."

    agents = {a["id"]: a["name"] for a in (await auth_client.get("/api/agents")).json()}
    tasks = (await auth_client.get(f"/api/runs/{run_id}/tasks")).json()
    assert [(t["key"], t["status"], agents[t["assigned_agent_id"]]) for t in tasks] == [
        ("T1", "COMPLETED", "Granite"),  # 'architecture': empate → 1.º participante
        ("T2", "COMPLETED", "Qwen"),  # 'coding': só o Qwen tem
    ]
    assert tasks[1]["depends_on"] == ["T1"]
    assert tasks[1]["iteration_count"] == 2  # execução + correção

    # Versionamento: a correção criou a v2, ligada ao mesmo autor.
    history = (
        await auth_client.get(
            f"/api/projects/{project_id}/files/history", params={"path": "src/app.py"}
        )
    ).json()
    assert [(v["version"], v["change_kind"]) for v in history] == [(1, "CREATE"), (2, "REVISION")]
    assert {agents[v["author_agent_id"]] for v in history} == {"Qwen"}
    content = (
        await auth_client.get(
            f"/api/projects/{project_id}/files/content", params={"path": "src/app.py"}
        )
    ).json()
    assert content["content"] == FIXED
    diff = (
        await auth_client.get(
            f"/api/projects/{project_id}/files/diff",
            params={"path": "src/app.py", "from_version": 1, "to_version": 2},
        )
    ).json()["diff"]
    assert "+    if qty < 0:" in diff

    # Revisões: T1 aprovada; T2 rejeitada e depois aprovada, sempre por outro agente.
    reviews = (await auth_client.get(f"/api/runs/{run_id}/reviews")).json()
    assert [
        (r["task_key"], r["round"], r["verdict"], agents[r["reviewer_agent_id"]]) for r in reviews
    ] == [
        ("T1", 1, "APPROVED", "Qwen"),
        ("T2", 1, "NEEDS_REVISION", "Granite"),
        ("T2", 2, "APPROVED", "Granite"),
    ]
    assert reviews[1]["issues"][0]["severity"] == "MAJOR"

    # Mensagens tipificadas guardadas.
    kinds = {m["kind"] for m in (await auth_client.get(f"/api/runs/{run_id}/messages")).json()}
    assert {"ORCHESTRATOR", "AGENT", "TASK_RESULT", "REVIEW"} <= kinds

    # Métricas reais: plano, 2 execuções, 1 correção, 3 revisões, relatório = 8 chamadas.
    metrics = (await auth_client.get(f"/api/runs/{run_id}/metrics")).json()
    assert metrics["api_calls"] == 8
    assert metrics["tasks_completed"] == 2
    assert metrics["reviews"] == 3 and metrics["revisions"] == 1
    assert metrics["estimated_cost_usd"] == 0.0

    async with app.state.db.sessionmaker() as session:
        types = set(
            await session.scalars(select(RunEvent.type).where(RunEvent.run_id == uuid.UUID(run_id)))
        )
    assert {
        "plan.created",
        "task.updated",
        "file.changed",
        "review.completed",
        "tool.called",
        "run.status",
        "run.finished",
    } <= types


async def test_reviewer_cannot_approve_with_major_issues(app, auth_client) -> None:
    def script(request):
        prompt = request.messages[0].content
        if "# Tarefa a rever" in prompt:
            return FakeResponse(
                tool_calls=[
                    (
                        "submit_review",
                        {
                            "verdict": "APPROVED",
                            "summary": "ok",
                            "issues": [{"severity": "CRITICAL", "description": "não funciona"}],
                        },
                    )
                ]
            )
        return team_script(request)

    use_providers(app, ollama=FakeProvider(script))
    project_id = await _project(auth_client)
    run = (
        await auth_client.post(f"/api/projects/{project_id}/runs", json={"objective": "x"})
    ).json()
    await _wait_finished(auth_client, run["id"], app)
    reviews = (await auth_client.get(f"/api/runs/{run['id']}/reviews")).json()
    assert reviews[0]["verdict"] == "NEEDS_REVISION"


async def test_revision_without_changes_stops_the_loop(app, auth_client) -> None:
    def script(request):
        prompt = request.messages[0].content
        if "# Revisão a corrigir" in prompt:  # "corrige" sem alterar nada
            return FakeResponse(tool_calls=[("submit_result", {"summary": "Não mudei nada."})])
        if "# Tarefa a rever" in prompt:
            return FakeResponse(
                tool_calls=[
                    (
                        "submit_review",
                        {
                            "verdict": "NEEDS_REVISION",
                            "summary": "mau",
                            "issues": [{"severity": "MAJOR", "description": "x"}],
                        },
                    )
                ]
            )
        return team_script(request)

    use_providers(app, ollama=FakeProvider(script))
    project_id = await _project(auth_client)
    run = (
        await auth_client.post(f"/api/projects/{project_id}/runs", json={"objective": "x"})
    ).json()
    await _wait_finished(auth_client, run["id"], app)
    messages = [
        m["content"] for m in (await auth_client.get(f"/api/runs/{run['id']}/messages")).json()
    ]
    assert any("sem progresso" in m for m in messages)


async def test_invalid_plan_falls_back_to_single_task(app, auth_client) -> None:
    cyclic = {
        "tasks": [
            {"key": "A", "title": "a", "description": "a", "depends_on": ["B"]},
            {"key": "B", "title": "b", "description": "b", "depends_on": ["A"]},
        ]
    }

    def script(request):
        prompt = request.messages[0].content
        if "Divide o objetivo" in prompt:
            return FakeResponse(tool_calls=[("submit_plan", cyclic)])
        if "# A tua tarefa: T1" in prompt:
            return FakeResponse(
                tool_calls=[
                    ("write_file", {"path": "main.py", "content": "print(1)"}),
                    ("submit_result", {"summary": "feito"}),
                ]
            )
        if "# Tarefa a rever" in prompt:
            return FakeResponse(
                tool_calls=[("submit_review", {"verdict": "APPROVED", "summary": "ok"})]
            )
        return team_script(request)

    provider = FakeProvider(script)
    use_providers(app, ollama=provider)
    project_id = await _project(auth_client)
    run = (
        await auth_client.post(f"/api/projects/{project_id}/runs", json={"objective": "x"})
    ).json()
    run = await _wait_finished(auth_client, run["id"], app)
    tasks = (await auth_client.get(f"/api/runs/{run['id']}/tasks")).json()
    assert [t["key"] for t in tasks] == ["T1"]
    assert run["status"] == "COMPLETED"
    # O planner recebeu o erro ("dependências circulares") para tentar corrigir.
    retries = [r for r in provider.requests if any("circulares" in m.content for m in r.messages)]
    assert retries


async def test_llm_call_limit_stops_the_run(app, auth_client) -> None:
    use_providers(app, ollama=FakeProvider(team_script))
    project_id = await _project(auth_client)
    run = (
        await auth_client.post(
            f"/api/projects/{project_id}/runs", json={"objective": "x", "autostart": False}
        )
    ).json()
    ctx = await app.state.run_manager.build_context(uuid.UUID(run["id"]))
    ctx.strategy = dataclasses.replace(
        ctx.strategy, limits=dataclasses.replace(ctx.strategy.limits, max_llm_calls=2)
    )
    await execute_run(ctx)
    final = (await auth_client.get(f"/api/runs/{run['id']}")).json()
    assert final["status"] == "FAILED"
    assert "chamadas" in final["failure_reason"]
    tasks = (await auth_client.get(f"/api/runs/{run['id']}/tasks")).json()
    assert all(t["status"] in ("COMPLETED", "CANCELLED") for t in tasks)


async def test_pause_resume_and_cancel(app, auth_client) -> None:
    use_providers(app, ollama=FakeProvider(team_script, delay_s=0.02))
    project_id = await _project(auth_client)
    run = (
        await auth_client.post(f"/api/projects/{project_id}/runs", json={"objective": "x"})
    ).json()
    run_id = run["id"]

    await asyncio.sleep(0.05)
    paused = (await auth_client.post(f"/api/runs/{run_id}/pause")).json()
    assert paused["status"] == "PAUSED"
    resumed = (await auth_client.post(f"/api/runs/{run_id}/resume")).json()
    assert resumed["status"] == "RUNNING"

    cancelled = (await auth_client.post(f"/api/runs/{run_id}/cancel")).json()
    assert cancelled["status"] == "CANCELLED"
    tasks = (await auth_client.get(f"/api/runs/{run_id}/tasks")).json()
    assert all(t["status"] in ("COMPLETED", "CANCELLED") for t in tasks)
    assert (await auth_client.post(f"/api/runs/{run_id}/pause")).status_code == 409


async def test_strategy_validation(auth_client) -> None:
    project_id = await _project(auth_client)
    unknown = await auth_client.post(
        f"/api/projects/{project_id}/runs", json={"objective": "x", "strategy_key": "magia"}
    )
    assert unknown.status_code == 422
    granite = (await auth_client.get("/api/agents")).json()[0]["id"]
    too_few = await auth_client.post(
        f"/api/projects/{project_id}/runs", json={"objective": "x", "agent_ids": [granite]}
    )
    assert too_few.status_code == 422  # a colaborativa precisa de 2 agentes
    strategies = [s["key"] for s in (await auth_client.get("/api/strategies")).json()]
    assert "collaborative" in strategies


async def test_unreachable_model_fails_the_run_with_a_clear_message(app, auth_client) -> None:
    from app.providers.base import ProviderError, ProviderErrorKind

    down = ProviderError(ProviderErrorKind.UNAVAILABLE, "ollama: Connection error.")
    use_providers(app, ollama=FakeProvider(lambda _r: FakeResponse(error=down)))
    run = await _start(auth_client, await _project(auth_client))
    final = await _wait_finished(auth_client, run["id"], app)
    assert final["status"] == "FAILED"
    assert "Ollama" in final["failure_reason"]
