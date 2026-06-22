"""
Tests del módulo de archivos generados.

Cubre los endpoints (ownership, 404, listado/lectura/edición) y, sobre todo,
prueba unitariamente el endurecimiento anti-path-traversal de _resolve_disk_path.
"""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.constants import CYPRESS_FEATURES_SUBDIR, CYPRESS_STEPS_SUBDIR
from backend.models.db import GeneratedFile
from backend.routers.files import _resolve_disk_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def execution_id(client, auth_headers):
    proj = await client.post(
        "/projects",
        headers=auth_headers,
        json={"name": "P", "description": "d", "jira_project_key": "ef"},
    )
    pid = proj.json()["id"]
    exe = await client.post(
        "/executions",
        headers=auth_headers,
        json={"project_id": pid, "ai_model": "gemini-pro-latest"},
    )
    return exe.json()["execution_id"]


async def _insert_file(db_engine, execution_id, name, content="contenido", ftype="gherkin"):
    Session = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        s.add(
            GeneratedFile(
                execution_id=execution_id, file_name=name, file_type=ftype, file_content=content
            )
        )
        await s.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
async def test_list_files_requires_auth(client, execution_id):
    resp = await client.get(f"/executions/{execution_id}/files")
    assert resp.status_code == 401


async def test_list_files_empty(client, auth_headers, execution_id):
    resp = await client.get(f"/executions/{execution_id}/files", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_file_not_found(client, auth_headers, execution_id):
    resp = await client.get(
        f"/executions/{execution_id}/files/inexistente.feature", headers=auth_headers
    )
    assert resp.status_code == 404


async def test_update_file_not_found(client, auth_headers, execution_id):
    resp = await client.patch(
        f"/executions/{execution_id}/files/x.ts",
        headers=auth_headers,
        json={"content": "nuevo"},
    )
    assert resp.status_code == 404


async def test_download_no_files_404(client, auth_headers, execution_id):
    resp = await client.get(f"/executions/{execution_id}/download", headers=auth_headers)
    assert resp.status_code == 404


async def test_other_user_cannot_list_files(client, auth_headers, execution_id):
    from backend.tests.conftest import _register_and_login

    other = await _register_and_login(client, "ajeno@quind.io")
    resp = await client.get(
        f"/executions/{execution_id}/files", headers={"Authorization": f"Bearer {other}"}
    )
    assert resp.status_code == 404


async def test_list_and_get_file(client, auth_headers, execution_id, db_engine):
    await _insert_file(db_engine, execution_id, "login.feature", content="Feature: login")

    listing = await client.get(f"/executions/{execution_id}/files", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    got = await client.get(
        f"/executions/{execution_id}/files/login.feature", headers=auth_headers
    )
    assert got.status_code == 200
    assert got.json()["file_content"] == "Feature: login"


async def test_update_file_content(client, auth_headers, execution_id, db_engine):
    await _insert_file(db_engine, execution_id, "steps.ts", content="old")
    resp = await client.patch(
        f"/executions/{execution_id}/files/steps.ts",
        headers=auth_headers,
        json={"content": "nuevo contenido"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"updated": "steps.ts"}
    # Confirma que se persistió
    got = await client.get(
        f"/executions/{execution_id}/files/steps.ts", headers=auth_headers
    )
    assert got.json()["file_content"] == "nuevo contenido"


# ---------------------------------------------------------------------------
# Anti path-traversal (unitario, sin DB) — el endurecimiento de seguridad
# ---------------------------------------------------------------------------
def test_resolve_valid_feature(tmp_path):
    resolved = _resolve_disk_path(tmp_path, "caso.feature")
    assert resolved.is_relative_to(tmp_path.resolve())
    assert str(CYPRESS_FEATURES_SUBDIR) in str(resolved)
    assert resolved.name == "caso.feature"


def test_resolve_valid_ts(tmp_path):
    resolved = _resolve_disk_path(tmp_path, "caso.ts")
    assert resolved.is_relative_to(tmp_path.resolve())
    assert str(CYPRESS_STEPS_SUBDIR) in str(resolved)
    assert resolved.name == "caso.ts"


def test_resolve_rejects_bad_extension(tmp_path):
    with pytest.raises(HTTPException) as exc:
        _resolve_disk_path(tmp_path, "malicioso.sh")
    assert exc.value.status_code == 400


@pytest.mark.parametrize(
    "evil",
    [
        "../../../etc/passwd.ts",
        "../secreto.feature",
        "sub/dir/x.ts",
        "/etc/passwd.ts",
    ],
)
def test_resolve_rejects_traversal(tmp_path, evil):
    with pytest.raises(HTTPException) as exc:
        _resolve_disk_path(tmp_path, evil)
    # Separadores → 400; ruta que se escapa tras resolver → 403
    assert exc.value.status_code in (400, 403)
