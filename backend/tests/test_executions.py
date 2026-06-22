"""
Tests del módulo de ejecuciones — ejercitan la capa de repositorios
(execution_repository) introducida en el refactor: create, ownership, listado
de endpoints, selección y los caminos de error.
"""
import pytest_asyncio


@pytest_asyncio.fixture
async def project_id(client, auth_headers):
    resp = await client.post(
        "/projects",
        headers=auth_headers,
        json={"name": "Proj", "description": "d", "jira_project_key": "ef"},
    )
    return resp.json()["id"]


@pytest_asyncio.fixture
async def execution_id(client, auth_headers, project_id):
    resp = await client.post(
        "/executions",
        headers=auth_headers,
        json={"project_id": project_id, "ai_model": "gemini-pro-latest"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["execution_id"]


async def test_create_execution_requires_auth(client, project_id):
    resp = await client.post(
        "/executions", json={"project_id": project_id, "ai_model": "gemini-pro-latest"}
    )
    assert resp.status_code == 401


async def test_create_execution(client, auth_headers, project_id):
    resp = await client.post(
        "/executions",
        headers=auth_headers,
        json={"project_id": project_id, "ai_model": "gemini-pro-latest"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "execution_id" in body
    assert body["status"] == "pending"


async def test_create_execution_unknown_project_404(client, auth_headers):
    """is_project_owned_by → proyecto inexistente debe dar 404."""
    resp = await client.post(
        "/executions",
        headers=auth_headers,
        json={
            "project_id": "00000000-0000-0000-0000-000000000000",
            "ai_model": "gemini-pro-latest",
        },
    )
    assert resp.status_code == 404


async def test_get_execution(client, auth_headers, execution_id):
    resp = await client.get(f"/executions/{execution_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["endpoints_selected"] == 0


async def test_get_execution_not_found(client, auth_headers):
    resp = await client.get("/executions/no-existe", headers=auth_headers)
    assert resp.status_code == 404


async def test_list_endpoints_empty(client, auth_headers, execution_id):
    resp = await client.get(f"/executions/{execution_id}/endpoints", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_update_endpoint_selection_empty(client, auth_headers, execution_id):
    resp = await client.patch(
        f"/executions/{execution_id}/endpoints",
        headers=auth_headers,
        json={"selected_ids": []},
    )
    assert resp.status_code == 200
    assert resp.json() == {"updated": 0}


async def test_generate_without_selection_400(client, auth_headers, execution_id):
    """list_selected_endpoints vacío → 400 (no hay endpoints seleccionados)."""
    resp = await client.post(
        f"/executions/{execution_id}/generate", headers=auth_headers, json={}
    )
    assert resp.status_code == 400


async def test_other_user_cannot_access_execution(client, auth_headers, execution_id):
    from backend.tests.conftest import _register_and_login

    other_token = await _register_and_login(client, "intruso@quind.io")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    resp = await client.get(f"/executions/{execution_id}", headers=other_headers)
    assert resp.status_code == 404


# --- fetch-jira: caso de uso extraído a execution_service ---
async def test_fetch_jira_requires_auth(client, execution_id):
    resp = await client.post(
        f"/executions/{execution_id}/fetch-jira", json={"issue_key": "EF-1"}
    )
    assert resp.status_code == 401


async def test_fetch_jira_unknown_execution_404(client, auth_headers):
    resp = await client.post(
        "/executions/no-existe/fetch-jira", headers=auth_headers, json={"issue_key": "EF-1"}
    )
    assert resp.status_code == 404


async def test_fetch_jira_without_credentials_424(client, auth_headers, execution_id):
    """Sin credenciales Jira guardadas → JiraCredentialsMissing → 424."""
    resp = await client.post(
        f"/executions/{execution_id}/fetch-jira",
        headers=auth_headers,
        json={"issue_key": "EF-1"},
    )
    assert resp.status_code == 424
