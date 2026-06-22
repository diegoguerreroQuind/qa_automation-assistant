"""
Credenciales / integraciones (Jira / Azure DevOps).

Arquitectura: Usuario → Proyectos → Integraciones/Credenciales → HU.
Relación 1:N — un proyecto tiene una credencial; una credencial puede estar en
varios proyectos. La creación ocurre desde el flujo de proyectos; la pestaña
Credenciales es de consulta/administración. La eliminación de una credencial
solo sucede cuando deja de tener proyectos asociados.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.db import Project, User
from backend.schemas.integrations import (
    IntegrationCreate,
    IntegrationOut,
    IntegrationTokenUpdate,
    LinkIntegrationRequest,
)
from backend.security.jwt import get_current_user
from backend.services import integrations_service as svc

router = APIRouter(tags=["integrations"])


async def _owned_project(db: AsyncSession, user: User, project_id: str) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


# ── Pestaña Credenciales: todas las credenciales del usuario (consulta) ──
@router.get("/integrations", response_model=list[IntegrationOut])
async def list_my_integrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await svc.list_user_integration_views(db, current_user.id)


# ── Credencial asociada a un proyecto (0 o 1) ──
@router.get("/projects/{project_id}/integrations", response_model=list[IntegrationOut])
async def list_project_integrations(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _owned_project(db, current_user, project_id)
    return await svc.list_project_integration_views(db, project_id)


@router.post(
    "/projects/{project_id}/integrations",
    response_model=IntegrationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_integration(
    project_id: str,
    body: IntegrationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Crea una credencial nueva y la asocia al proyecto (reemplaza la anterior)."""
    await _owned_project(db, current_user, project_id)

    if body.provider != "jira":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La integración con Azure DevOps aún está en desarrollo.",
        )

    required = svc.REQUIRED_KEYS[body.provider]
    missing = [k for k in required if not body.values.get(k, "").strip()]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Faltan campos obligatorios: {', '.join(missing)}",
        )

    values = {k: v.strip() for k, v in body.values.items() if v and v.strip()}
    integration = await svc.create_integration(
        db, current_user.id, body.provider, body.name, values
    )
    await svc.set_project_credential(db, project_id, integration.id)
    return await svc._to_view(db, integration)


@router.post(
    "/projects/{project_id}/integrations/link",
    response_model=IntegrationOut,
    status_code=status.HTTP_200_OK,
)
async def link_existing_integration(
    project_id: str,
    body: LinkIntegrationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reutiliza una credencial existente como la del proyecto (reemplaza la anterior)."""
    await _owned_project(db, current_user, project_id)
    integration = await svc.get_integration_owned(db, current_user.id, body.integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Credencial no encontrada")
    await svc.set_project_credential(db, project_id, integration.id)
    return await svc._to_view(db, integration)


@router.delete("/projects/{project_id}/integrations", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_project_integration(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Desasocia la credencial del proyecto (se elimina si queda huérfana)."""
    await _owned_project(db, current_user, project_id)
    await svc.unlink_project_credential(db, project_id)


@router.patch("/integrations/{integration_id}/token", response_model=IntegrationOut)
async def update_integration_token(
    integration_id: str,
    body: IntegrationTokenUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Renueva únicamente el token/PAT (server/email permanecen inmutables)."""
    integration = await svc.get_integration_owned(db, current_user.id, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Credencial no encontrada")
    key_name = svc.TOKEN_KEY.get(integration.provider, "token")
    await svc.update_secret(db, integration, key_name, body.value.strip())
    return await svc._to_view(db, integration)
