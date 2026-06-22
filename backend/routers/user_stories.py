"""
Historias de Usuario (HU) por proyecto.

Arquitectura: Proyecto → Credencial → Historias de Usuario sincronizadas.

Contrato de sincronización (equivalente al body que el frontend envía):
  {
    "project_key": "<project.jira_project_key>",
    "status_categories": ["In Progress"],
    "only_mine": false,
    "only_open_sprints": true
  }

- POST /projects/{id}/user-stories/sync: lee las credenciales Jira DEL PROYECTO,
  consulta Jira usando statusCategory ("In Progress") dentro de sprints abiertos,
  y persiste cada HU asociada al proyecto.
- GET  /projects/{id}/user-stories: devuelve las HU ya almacenadas (sin Jira).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.db import JiraIssue, Project, User
from backend.schemas.user_stories import UserStoriesResponse, UserStoryOut
from backend.security.jwt import get_current_user
from backend.services.integrations_service import get_project_jira_credentials
from backend.services.jira_persistence import upsert_project_jira_issue
from backend.services.jira_service import JiraService

router = APIRouter(tags=["user-stories"])
logger = logging.getLogger("qa_assistant.user_stories")

# Categorías de estado del tablero Jira que se importan.
# Usar statusCategory (estable entre workflows) en lugar de nombres de estado
# concretos (frágiles / dependen del idioma del workspace Jira).
# "In Progress" equivale a la columna "En curso" del tablero.
SYNC_STATUS_CATEGORIES = ["In Progress"]

_CREDS_MISSING = (
    "El proyecto no tiene una credencial Jira asociada. "
    "Configura una credencial en el proyecto antes de sincronizar."
)
_NO_PROJECT_KEY = (
    "El proyecto no tiene configurada la clave del proyecto Jira (ej. 'EF'). "
    "Edita el proyecto y añade la clave Jira antes de sincronizar."
)


async def _owned_project(db: AsyncSession, user: User, project_id: str) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


def _to_story(issue: JiraIssue) -> UserStoryOut:
    return UserStoryOut(
        id=issue.id,
        issue_key=issue.issue_key,
        summary=issue.summary,
        status=issue.status,
        description=issue.description,
        acceptance_criteria=issue.structured_criteria,
    )


async def _stored_response(db: AsyncSession, project_id: str) -> UserStoriesResponse:
    rows = (
        await db.execute(
            select(JiraIssue)
            .where(JiraIssue.project_id == project_id)
            .order_by(JiraIssue.issue_key.asc())
        )
    ).scalars().all()
    return UserStoriesResponse(stories=[_to_story(r) for r in rows], total=len(rows))


@router.get("/projects/{project_id}/user-stories", response_model=UserStoriesResponse)
async def list_user_stories(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """HU ya almacenadas para el proyecto (carga rápida, sin llamar a Jira)."""
    await _owned_project(db, current_user, project_id)
    return await _stored_response(db, project_id)


@router.post(
    "/projects/{project_id}/user-stories/sync",
    response_model=UserStoriesResponse,
    responses={
        424: {"description": "El proyecto no tiene credencial Jira"},
        422: {"description": "El proyecto no tiene clave Jira configurada"},
    },
)
async def sync_user_stories(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sincroniza desde Jira las HU usando las credenciales del proyecto.

    JQL generado (equivalente al contrato del frontend):
        project = "<jira_project_key>"
        AND statusCategory in ("In Progress")
        AND sprint in openSprints()
        ORDER BY updated DESC

    Persiste cada HU en la tabla jira_tickets asociada al proyecto_id.
    """
    project = await _owned_project(db, current_user, project_id)

    # Validar que el proyecto tiene clave Jira configurada
    if not project.jira_project_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_NO_PROJECT_KEY,
        )

    # Obtener credenciales Jira del proyecto
    creds = await get_project_jira_credentials(db, project_id)
    if not creds:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=_CREDS_MISSING)

    try:
        service = JiraService(server=creds["server"], email=creds["email"], token=creds["token"])
        tickets = service.get_filtered_tickets(
            project_key=project.jira_project_key,
            status_categories=SYNC_STATUS_CATEGORIES,
            statuses=None,          # Usar statusCategory (robusto, no depende del idioma)
            assignee_email=None,    # only_mine=false → traer todas las HUs
            only_open_sprints=True,
        )
        for ticket in tickets:
            await upsert_project_jira_issue(db, project_id, current_user.id, ticket)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error consultando Jira: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo consultar Jira. Revisa las credenciales e inténtalo de nuevo.",
        )

    return await _stored_response(db, project_id)

