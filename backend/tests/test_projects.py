"""Tests del módulo de proyectos (CRUD + ownership + serialización batch)."""
import pytest_asyncio


@pytest_asyncio.fixture
async def project_id(client, auth_headers):
    resp = await client.post(
        "/projects",
        headers=auth_headers,
        json={"name": "Proj", "description": "desc", "jira_project_key": "ef"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_list_projects_requires_auth(client):
    resp = await client.get("/projects")
    assert resp.status_code == 401


async def test_list_projects_empty(client, auth_headers):
    resp = await client.get("/projects", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_project(client, auth_headers):
    resp = await client.post(
        "/projects",
        headers=auth_headers,
        json={"name": "Mi Proyecto", "description": "x", "jira_project_key": "ab"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Mi Proyecto"
    # jira_project_key se normaliza a mayúsculas
    assert body["jira_project_key"] == "AB"
    assert body["credential"] is None


async def test_list_projects_after_create(client, auth_headers, project_id):
    resp = await client.get("/projects", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == project_id


async def test_get_project_not_found(client, auth_headers):
    resp = await client.get("/projects/no-existe", headers=auth_headers)
    assert resp.status_code == 404


async def test_update_project(client, auth_headers, project_id):
    resp = await client.put(
        f"/projects/{project_id}",
        headers=auth_headers,
        json={"name": "Renombrado", "description": "nueva", "jira_project_key": "ZZ"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Renombrado"


async def test_delete_project(client, auth_headers, project_id):
    resp = await client.delete(f"/projects/{project_id}", headers=auth_headers)
    assert resp.status_code == 204
    # Ya no aparece en el listado
    listing = await client.get("/projects", headers=auth_headers)
    assert listing.json() == []


async def test_other_user_cannot_see_project(client, auth_headers, project_id):
    """El proyecto de un usuario no es visible ni accesible para otro."""
    from backend.tests.conftest import _register_and_login

    other_token = await _register_and_login(client, "otro@quind.io")
    other_headers = {"Authorization": f"Bearer {other_token}"}

    listing = await client.get("/projects", headers=other_headers)
    assert listing.json() == []

    resp = await client.get(f"/projects/{project_id}", headers=other_headers)
    assert resp.status_code == 404
