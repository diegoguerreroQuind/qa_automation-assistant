"""Tests del módulo de autenticación (register / login / me / 401)."""


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_register_returns_user(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "nuevo@quind.io", "name": "Nuevo", "password": "Test1234!"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "nuevo@quind.io"
    assert body["role"] == "qa"
    assert "id" in body


async def test_register_duplicate_email_conflicts(client):
    payload = {"email": "dup@quind.io", "name": "Dup", "password": "Test1234!"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409


async def test_login_returns_token(client):
    await client.post(
        "/auth/register",
        json={"email": "login@quind.io", "name": "Login", "password": "Test1234!"},
    )
    resp = await client.post(
        "/auth/login", json={"email": "login@quind.io", "password": "Test1234!"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


async def test_login_wrong_password_unauthorized(client):
    await client.post(
        "/auth/register",
        json={"email": "wrong@quind.io", "name": "Wrong", "password": "Test1234!"},
    )
    resp = await client.post(
        "/auth/login", json={"email": "wrong@quind.io", "password": "incorrecta"}
    )
    assert resp.status_code == 401


async def test_me_requires_auth(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_with_token(client, auth_headers):
    resp = await client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "tester@quind.io"
