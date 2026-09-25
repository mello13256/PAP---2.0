import io
import uuid
import zipfile

import pytest

from app.workspace import service
from app.workspace.service import Author, WorkspaceConflictError


async def _project(client) -> str:
    return (await client.post("/api/projects", json={"name": "Loja"})).json()["id"]


async def test_versions_conflicts_and_no_op_writes(app, auth_client) -> None:
    project_id = uuid.UUID(await _project(auth_client))
    agent_a = Author(agent_id=None, user_id=None)
    async with app.state.db.sessionmaker() as session:
        first = await service.write_file(
            session, project_id, "src/api.py", "v1", author=agent_a, base_version=None
        )
        assert first.created and first.version.version_number == 1

        # Outro agente escreve sem ter lido a versão atual → conflito (nada é sobrescrito).
        with pytest.raises(WorkspaceConflictError):
            await service.write_file(
                session, project_id, "src/api.py", "outro", author=agent_a, base_version=None
            )

        second = await service.write_file(
            session, project_id, "src/api.py", "v2", author=agent_a, base_version=1
        )
        assert second.version.version_number == 2

        # Conteúdo igual → nenhuma versão nova.
        same = await service.write_file(
            session, project_id, "src/api.py", "v2", author=agent_a, base_version=2
        )
        assert not same.changed

        # Basear-se numa versão antiga → conflito.
        with pytest.raises(WorkspaceConflictError):
            await service.write_file(
                session, project_id, "src/api.py", "v3", author=agent_a, base_version=1
            )


async def test_workspace_api(auth_client, settings) -> None:
    project_id = await _project(auth_client)
    url = f"/api/projects/{project_id}/files"

    created = await auth_client.put(url, json={"path": "README.md", "content": "# Loja\n"})
    assert created.status_code == 200, created.text
    assert created.json()["version"] == 1

    conflict = await auth_client.put(url, json={"path": "README.md", "content": "x"})
    assert conflict.status_code == 409

    await auth_client.put(
        url, json={"path": "README.md", "content": "# Loja\nInventário\n", "base_version": 1}
    )
    listed = (await auth_client.get(url)).json()
    assert [(f["path"], f["version"]) for f in listed] == [("README.md", 2)]

    old = (
        await auth_client.get(f"{url}/content", params={"path": "README.md", "version": 1})
    ).json()
    assert old["content"] == "# Loja\n" and old["current_version"] == 2

    diff = (
        await auth_client.get(
            f"{url}/diff", params={"path": "README.md", "from_version": 1, "to_version": 2}
        )
    ).json()["diff"]
    assert "+Inventário" in diff

    bad = await auth_client.put(url, json={"path": "../fora.py", "content": "x"})
    assert bad.status_code == 400

    exported = await auth_client.get(f"{url}/export")
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        assert archive.read("README.md").decode() == "# Loja\nInventário\n"

    # Espelho em disco.
    mirrored = settings.workspaces_dir / project_id / "README.md"
    assert mirrored.read_text(encoding="utf-8") == "# Loja\nInventário\n"
