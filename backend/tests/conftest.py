"""
Fixtures compartidas para los tests de la API.

Estrategia:
  - DB SQLite en memoria (StaticPool → una sola conexión compartida entre
    sesiones, para que todas vean la misma base efímera). Los modelos son
    compatibles con SQLite (sin tipos Postgres-específicos).
  - Se sobreescribe la dependencia `get_db` para usar la sesión de test.
  - La app se ejercita vía httpx ASGITransport SIN lifespan: no se levanta el
    scheduler ni el `init_db` real; las tablas se crean en la fixture.
  - La revocación de tokens (que pega a Redis) se mockea para que los tests no
    dependan de un Redis corriendo.
"""
import os

# Asegura un SECRET_KEY antes de importar settings (p.ej. en CI sin .env).
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use")
os.environ.setdefault("ENVIRONMENT", "development")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import backend.security.jwt as jwt_module
from backend.main import app
from backend.models.database import get_db
from backend.models.db import Base


@pytest_asyncio.fixture
async def db_engine():
    """Engine SQLite en memoria con todas las tablas creadas; se descarta al final."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite no enforcea FKs por defecto; activarlo hace que los tests ejerciten
    # el cascade/SET-NULL real (como Postgres), validando passive_deletes.
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine, monkeypatch):
    """Cliente HTTP async contra la app, con get_db apuntando a la DB de test."""
    TestSession = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db():
        async with TestSession() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    # Sin esto, decode_token → is_token_revoked pegaría a Redis en cada request.
    monkeypatch.setattr(jwt_module, "is_token_revoked", lambda token: False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def _register_and_login(client: AsyncClient, email: str, password: str = "Test1234!") -> str:
    await client.post(
        "/auth/register", json={"email": email, "name": "Tester", "password": password}
    )
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def auth_headers(client):
    """Headers Authorization de un usuario recién registrado."""
    token = await _register_and_login(client, "tester@quind.io")
    return {"Authorization": f"Bearer {token}"}
