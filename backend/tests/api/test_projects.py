from tests.conftest import register


async def test_project_crud(auth_client) -> None:
    created = await auth_client.post(
        "/api/projects", json={"name": "  Inventário  ", "description": "Loja"}
    )
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "Inventário"
    assert project["status"] == "ACTIVE"
    assert project["created_at"] == project["updated_at"]

    listed = await auth_client.get("/api/projects")
    assert [p["id"] for p in listed.json()] == [project["id"]]

    updated = await auth_client.patch(
        f"/api/projects/{project['id']}", json={"description": "Loja de bairro"}
    )
    assert updated.json()["description"] == "Loja de bairro"
    assert updated.json()["name"] == "Inventário"

    archived = await auth_client.delete(f"/api/projects/{project['id']}")
    assert archived.json()["status"] == "ARCHIVED"
    assert (await auth_client.get("/api/projects")).json() == []
    all_projects = await auth_client.get("/api/projects", params={"include_archived": True})
    assert len(all_projects.json()) == 1


async def test_projects_require_authentication(client) -> None:
    assert (await client.get("/api/projects")).status_code == 401
    assert (await client.post("/api/projects", json={"name": "X"})).status_code == 401


async def test_user_cannot_access_another_users_project(make_client) -> None:
    alice = await make_client()
    await register(alice, "alice@example.com")
    project = (await alice.post("/api/projects", json={"name": "Secreto"})).json()

    bob = await make_client()
    await register(bob, "bob@example.com")
    url = f"/api/projects/{project['id']}"

    # 404, não 403: o Bob nem fica a saber que o projeto existe.
    assert (await bob.get(url)).status_code == 404
    assert (await bob.patch(url, json={"name": "Roubado"})).status_code == 404
    assert (await bob.delete(url)).status_code == 404
    assert (await bob.get("/api/projects")).json() == []
    assert (await alice.get(url)).json()["name"] == "Secreto"


async def test_project_name_validation(auth_client) -> None:
    assert (await auth_client.post("/api/projects", json={"name": ""})).status_code == 422
    assert (await auth_client.post("/api/projects", json={"name": "x" * 121})).status_code == 422
