"""
Repositorio del dominio de archivos generados (GeneratedFile).

Encapsula el acceso a SQLAlchemy que antes vivía inline en `routers/files.py`.
La verificación de ownership de la ejecución se reutiliza desde
`execution_repository` (misma query) en vez de duplicarla.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import GeneratedFile


async def list_for_execution(db: AsyncSession, execution_id: str) -> list[GeneratedFile]:
    result = await db.execute(
        select(GeneratedFile).where(GeneratedFile.execution_id == execution_id)
    )
    return list(result.scalars().all())


async def get_by_name(
    db: AsyncSession, execution_id: str, filename: str
) -> GeneratedFile | None:
    result = await db.execute(
        select(GeneratedFile).where(
            GeneratedFile.execution_id == execution_id,
            GeneratedFile.file_name == filename,
        )
    )
    return result.scalar_one_or_none()


async def update_content(db: AsyncSession, gf: GeneratedFile, content: str) -> None:
    """Sobrescribe el contenido; `updated_at` se refresca solo (onupdate)."""
    gf.file_content = content
    await db.commit()
