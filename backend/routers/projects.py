from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_db
from backend.models.db import User, UserRole, Project
from backend.repositories import execution_repository as execution_repo
from backend.repositories import project_repository as project_repo
from backend.schemas.projects import (
    ProjectCreate, ProjectUpdate, ProjectOut, ExecutionSummary, CredentialRef,
)
from backend.security.jwt import get_current_user
from backend.services import integrations_service as integrations_svc

router = APIRouter(prefix="/projects", tags=["projects"])


def _normalize_key(jira_project_key: str | None) -> str | None:
    """Las claves de proyecto Jira se guardan en mayúsculas y sin espacios."""
    return jira_project_key.strip().upper() if jira_project_key else None


def _serialize_project(project: Project, integration) -> ProjectOut:
    """Construye el ProjectOut a partir de un proyecto y su integración (ya resuelta)."""
    credential = (
        CredentialRef(
            id=integration.id,
            name=integration.name or integration.label,
            provider=integration.provider,
        )
        if integration
        else None
    )
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        jira_project_key=project.jira_project_key,
        created_at=project.created_at,
        credential=credential,
    )


async def _project_out(db: AsyncSession, project: Project) -> ProjectOut:
    """Serializa un proyecto resolviendo su credencial con una query puntual."""
    integration = await integrations_svc.get_project_integration(db, project.id)
    return _serialize_project(project, integration)


async def _require_owned_project(project_id: str, user_id: str, db: AsyncSession) -> Project:
    project = await project_repo.get_for_user(db, project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await project_repo.create(
        db,
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        jira_project_key=_normalize_key(body.jira_project_key),
    )
    return await _project_out(db, project)


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    projects = await project_repo.list_for_user(db, current_user.id)
    # Resuelve todas las credenciales en UNA query (evita N+1 al listar).
    integrations = await integrations_svc.get_project_integrations_map(
        db, [p.id for p in projects]
    )
    return [_serialize_project(p, integrations.get(p.id)) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _require_owned_project(project_id, current_user.id, db)
    return await _project_out(db, project)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza nombre y descripción. La credencial se gestiona vía /integrations."""
    project = await _require_owned_project(project_id, current_user.id, db)
    project = await project_repo.update_fields(
        db,
        project,
        name=body.name,
        description=body.description,
        jira_project_key=_normalize_key(body.jira_project_key),
    )
    return await _project_out(db, project)


@router.get("/{project_id}/executions", response_model=list[ExecutionSummary])
async def list_executions(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_owned_project(project_id, current_user.id, db)
    return await execution_repo.list_for_project(db, project_id)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Elimina un proyecto y sus asociaciones (cascade). Las credenciales que queden
    sin ningún proyecto asociado se eliminan automáticamente; las compartidas con
    otros proyectos se conservan.

    RBAC: admin puede borrar cualquiera; qa solo los propios.
    """
    project = await project_repo.get_deletable_for(
        db, project_id, user_id=current_user.id, is_admin=current_user.role == UserRole.admin
    )
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    owner_id = project.user_id
    await project_repo.delete(db, project)
    await integrations_svc.cleanup_orphan_integrations(db, owner_id)
