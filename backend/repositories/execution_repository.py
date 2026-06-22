"""
Repositorio del dominio de Ejecuciones.

Encapsula todo el acceso a SQLAlchemy de Execution / Endpoint / ownership de
Project que antes vivía inline en `routers/executions.py`. No conoce HTTP: las
funciones devuelven datos o None y dejan que el router traduzca a respuestas /
excepciones HTTP.
"""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import Endpoint, Execution, Project


# ---------------------------------------------------------------------------
# Ownership / lectura
# ---------------------------------------------------------------------------
async def is_project_owned_by(db: AsyncSession, project_id: str, user_id: str) -> bool:
    """True si el proyecto existe y pertenece al usuario."""
    result = await db.execute(
        select(Project.id).where(Project.id == project_id, Project.user_id == user_id)
    )
    return result.scalar_one_or_none() is not None


async def get_execution_for_user(
    db: AsyncSession, execution_id: str, user_id: str
) -> Execution | None:
    """La ejecución, solo si pertenece (vía proyecto) al usuario."""
    result = await db.execute(
        select(Execution)
        .join(Project, Execution.project_id == Project.id)
        .where(Execution.id == execution_id, Project.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_endpoints(db: AsyncSession, execution_id: str) -> list[Endpoint]:
    result = await db.execute(
        select(Endpoint).where(Endpoint.execution_id == execution_id)
    )
    return list(result.scalars().all())


async def list_selected_endpoints(db: AsyncSession, execution_id: str) -> list[Endpoint]:
    result = await db.execute(
        select(Endpoint).where(
            Endpoint.execution_id == execution_id,
            Endpoint.selected.is_(True),
        )
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------
async def create_execution(
    db: AsyncSession, *, project_id: str, jira_ticket_id: str | None, ai_model: str
) -> Execution:
    execution = Execution(
        project_id=project_id,
        jira_ticket_id=jira_ticket_id,
        ai_model=ai_model,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    return execution


async def apply_endpoint_selection(
    db: AsyncSession, execution_id: str, selected_ids: list[int]
) -> None:
    """Deselecciona todos, selecciona los elegidos y actualiza el contador."""
    await db.execute(
        update(Endpoint)
        .where(Endpoint.execution_id == execution_id)
        .values(selected=False)
    )
    if selected_ids:
        await db.execute(
            update(Endpoint)
            .where(
                Endpoint.execution_id == execution_id,
                Endpoint.id.in_(selected_ids),
            )
            .values(selected=True)
        )
    await db.execute(
        update(Execution)
        .where(Execution.id == execution_id)
        .values(endpoints_selected=len(selected_ids))
    )
    await db.commit()


async def set_jira_context(
    db: AsyncSession,
    execution_id: str,
    *,
    issue_key: str,
    summary: str,
    jira_issue_id: str | None,
) -> None:
    """Vincula el ticket Jira y su resumen de negocio a la ejecución."""
    await db.execute(
        update(Execution)
        .where(Execution.id == execution_id)
        .values(
            jira_ticket_id=issue_key,
            jira_ticket_summary=summary,
            jira_issue_id=jira_issue_id,
        )
    )
    await db.commit()
