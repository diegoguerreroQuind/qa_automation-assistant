from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.database import get_db
from backend.models.db import User, UserRole, Project, Execution
from backend.schemas.projects import (
    ProjectCreate, ProjectUpdate, ProjectOut, ExecutionSummary, CredentialRef,
)
from backend.security.jwt import get_current_user
from backend.services import integrations_service as integrations_svc

router = APIRouter(prefix="/projects", tags=["projects"])


async def _project_out(db: AsyncSession, project: Project) -> ProjectOut:
    """Serializa un proyecto incluyendo su credencial asociada (si la tiene)."""
    integration = await integrations_svc.get_project_integration(db, project.id)
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


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        jira_project_key=body.jira_project_key.strip().upper() if body.jira_project_key else None,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _project_out(db, project)


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.user_id == current_user.id).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return [await _project_out(db, p) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return await _project_out(db, project)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza nombre y descripción. La credencial se gestiona vía /integrations."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    project.name = body.name
    project.description = body.description
    project.jira_project_key = body.jira_project_key.strip().upper() if body.jira_project_key else None
    await db.commit()
    await db.refresh(project)
    return await _project_out(db, project)


@router.get("/{project_id}/executions", response_model=list[ExecutionSummary])
async def list_executions(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    result = await db.execute(
        select(Execution)
        .where(Execution.project_id == project_id)
        .order_by(Execution.created_at.desc())
    )
    return result.scalars().all()


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
    where_clause = [Project.id == project_id]
    if current_user.role != UserRole.admin:
        where_clause.append(Project.user_id == current_user.id)

    result = await db.execute(select(Project).where(*where_clause))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    owner_id = project.user_id
    await db.delete(project)
    await db.commit()
    await integrations_svc.cleanup_orphan_integrations(db, owner_id)
