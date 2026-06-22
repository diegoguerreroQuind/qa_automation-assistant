"""
Repositorio del dominio de Proyectos.

Encapsula el acceso a SQLAlchemy de Project (CRUD + ownership, incluido el caso
admin) que antes vivía inline en `routers/projects.py`. No conoce HTTP: devuelve
datos o None y deja que el router traduzca a respuestas / excepciones.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import Project


async def create(
    db: AsyncSession,
    *,
    user_id: str,
    name: str,
    description: str | None,
    jira_project_key: str | None,
) -> Project:
    project = Project(
        user_id=user_id,
        name=name,
        description=description,
        jira_project_key=jira_project_key,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def get_for_user(db: AsyncSession, project_id: str, user_id: str) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_for_user(db: AsyncSession, user_id: str) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def update_fields(
    db: AsyncSession,
    project: Project,
    *,
    name: str,
    description: str | None,
    jira_project_key: str | None,
) -> Project:
    project.name = name
    project.description = description
    project.jira_project_key = jira_project_key
    await db.commit()
    await db.refresh(project)
    return project


async def get_deletable_for(
    db: AsyncSession, project_id: str, *, user_id: str, is_admin: bool
) -> Project | None:
    """
    Proyecto borrable por el actor: admin puede borrar cualquiera; el resto solo
    los propios. Devuelve None si no existe o no tiene permiso.
    """
    clauses = [Project.id == project_id]
    if not is_admin:
        clauses.append(Project.user_id == user_id)
    result = await db.execute(select(Project).where(*clauses))
    return result.scalar_one_or_none()


async def delete(db: AsyncSession, project: Project) -> None:
    await db.delete(project)
    await db.commit()
