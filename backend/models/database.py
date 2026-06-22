import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.config import settings
from backend.models.db import Base

logger = logging.getLogger("qa_assistant.db")


engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    future=True,
    # Pool settings for GCP Cloud SQL
    pool_pre_ping=True,
    pool_recycle=300,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """
    Crea las tablas que falten al arrancar — SOLO fuera de producción.

    En producción el esquema lo gestiona EXCLUSIVAMENTE Alembic (`alembic upgrade
    head`). Ejecutar `create_all` junto a las migraciones provoca drift: las tablas
    quedan creadas sin registrarse en `alembic_version` y las migraciones fallan o
    divergen (enums, tipos). Por eso aquí se omite en producción.
    """
    if settings.environment == "production":
        logger.info("init_db omitido en producción: el esquema lo gestiona Alembic")
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
