"""
Service layer para integraciones (Jira / Azure DevOps / futuros).

Arquitectura: Usuario → Proyectos → Integraciones/Credenciales → HU.

Relación: un proyecto tiene como máximo UNA credencial; una credencial puede
estar asociada a VARIOS proyectos (1:N). Los valores se guardan cifrados
(AES-256-GCM). Los valores SECRETOS (token/pat) NUNCA se devuelven al cliente;
los de IDENTIDAD (server, email…) sí, en modo lectura.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import Integration, IntegrationSecret, Project, ProjectIntegration
from backend.security.encryption import decrypt, encrypt

SECRET_KEYS = {"token", "api_key", "pat", "client_secret"}

IDENTITY_KEYS = {
    "jira": ["server", "email"],
    "azure": ["organization", "email"],
}

REQUIRED_KEYS = {
    "jira": ["server", "email", "token"],
    "azure": ["organization", "email", "pat"],
}

TOKEN_KEY = {"jira": "token", "azure": "pat"}


async def _secrets_for(db: AsyncSession, integration_id: str) -> list[IntegrationSecret]:
    result = await db.execute(
        select(IntegrationSecret).where(IntegrationSecret.integration_id == integration_id)
    )
    return list(result.scalars().all())


async def _projects_for(db: AsyncSession, integration_id: str) -> list[dict]:
    result = await db.execute(
        select(Project.id, Project.name)
        .join(ProjectIntegration, ProjectIntegration.project_id == Project.id)
        .where(ProjectIntegration.integration_id == integration_id)
        .order_by(Project.created_at.asc())
    )
    return [{"id": row.id, "name": row.name} for row in result.all()]


def _status(provider: str, keys: set[str]) -> str:
    token_key = TOKEN_KEY.get(provider, "token")
    return "active" if token_key in keys else "incomplete"


async def _to_view(db: AsyncSession, integration: Integration) -> dict:
    """Vista segura de una integración (identidad visible, secretos ocultos)."""
    secrets = await _secrets_for(db, integration.id)
    by_key = {s.key_name: s for s in secrets}
    identity: dict[str, str] = {}
    for key in IDENTITY_KEYS.get(integration.provider, []):
        if key in by_key:
            identity[key] = decrypt(by_key[key].encrypted_value)
    return {
        "id": integration.id,
        "name": integration.name or integration.label,
        "provider": integration.provider,
        "label": integration.label,
        "identity": identity,
        "keys": sorted(by_key.keys()),
        "status": _status(integration.provider, set(by_key.keys())),
        "created_at": integration.created_at,
        "updated_at": integration.updated_at,
        "projects": await _projects_for(db, integration.id),
    }


def _build_label(provider: str, values: dict[str, str]) -> str:
    if provider == "jira":
        host = (values.get("server") or "").replace("https://", "").replace("http://", "").rstrip("/")
        email = values.get("email") or ""
        return f"{host} · {email}".strip(" ·") or "Jira"
    if provider == "azure":
        return values.get("organization") or "Azure DevOps"
    return provider


# ---------------------------------------------------------------------------
# Creación / asociación
# ---------------------------------------------------------------------------
async def create_integration(
    db: AsyncSession, user_id: str, provider: str, name: str, values: dict[str, str]
) -> Integration:
    integration = Integration(
        user_id=user_id,
        provider=provider,
        name=name.strip() or _build_label(provider, values),
        label=_build_label(provider, values),
    )
    db.add(integration)
    await db.flush()
    for key, value in values.items():
        if value:
            db.add(
                IntegrationSecret(
                    integration_id=integration.id,
                    key_name=key,
                    encrypted_value=encrypt(value),
                )
            )
    await db.commit()
    await db.refresh(integration)
    return integration


async def get_project_integration(db: AsyncSession, project_id: str) -> Integration | None:
    """La (única) credencial asociada al proyecto, o None."""
    result = await db.execute(
        select(Integration)
        .join(ProjectIntegration, ProjectIntegration.integration_id == Integration.id)
        .where(ProjectIntegration.project_id == project_id)
    )
    return result.scalar_one_or_none()


async def set_project_credential(db: AsyncSession, project_id: str, integration_id: str) -> None:
    """
    Asocia (reemplazando) la credencial del proyecto. Como un proyecto solo
    admite una credencial, elimina el enlace previo y limpia la credencial
    anterior si queda huérfana.
    """
    existing = await db.execute(
        select(ProjectIntegration).where(ProjectIntegration.project_id == project_id)
    )
    previous_integration_id: str | None = None
    for link in existing.scalars().all():
        previous_integration_id = link.integration_id
        await db.delete(link)
    await db.flush()

    db.add(ProjectIntegration(project_id=project_id, integration_id=integration_id))
    await db.commit()

    if previous_integration_id and previous_integration_id != integration_id:
        await _delete_if_orphan(db, previous_integration_id)


async def unlink_project_credential(db: AsyncSession, project_id: str) -> None:
    result = await db.execute(
        select(ProjectIntegration).where(ProjectIntegration.project_id == project_id)
    )
    removed: list[str] = []
    for link in result.scalars().all():
        removed.append(link.integration_id)
        await db.delete(link)
    await db.commit()
    for integration_id in removed:
        await _delete_if_orphan(db, integration_id)


# ---------------------------------------------------------------------------
# Lecturas
# ---------------------------------------------------------------------------
async def list_project_integration_views(db: AsyncSession, project_id: str) -> list[dict]:
    integration = await get_project_integration(db, project_id)
    return [await _to_view(db, integration)] if integration else []


async def list_user_integration_views(db: AsyncSession, user_id: str) -> list[dict]:
    """Todas las credenciales del usuario (para la pestaña de consulta)."""
    result = await db.execute(
        select(Integration)
        .where(Integration.user_id == user_id)
        .order_by(Integration.created_at.desc())
    )
    return [await _to_view(db, i) for i in result.scalars().all()]


async def get_integration_owned(
    db: AsyncSession, user_id: str, integration_id: str
) -> Integration | None:
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id, Integration.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Mutaciones de secretos / limpieza
# ---------------------------------------------------------------------------
async def update_secret(db: AsyncSession, integration: Integration, key_name: str, value: str) -> None:
    """Actualiza el valor cifrado (ej. renovar token) y marca updated_at."""
    result = await db.execute(
        select(IntegrationSecret).where(
            IntegrationSecret.integration_id == integration.id,
            IntegrationSecret.key_name == key_name,
        )
    )
    secret = result.scalar_one_or_none()
    if secret:
        secret.encrypted_value = encrypt(value)
    else:
        db.add(
            IntegrationSecret(
                integration_id=integration.id, key_name=key_name, encrypted_value=encrypt(value)
            )
        )
    # Forzar onupdate de updated_at.
    integration.label = integration.label
    await db.commit()
    await db.refresh(integration)


async def _delete_if_orphan(db: AsyncSession, integration_id: str) -> None:
    links = await db.execute(
        select(ProjectIntegration.id).where(ProjectIntegration.integration_id == integration_id)
    )
    if links.first() is None:
        integration = await db.get(Integration, integration_id)
        if integration:
            await db.delete(integration)
            await db.commit()


async def cleanup_orphan_integrations(db: AsyncSession, user_id: str) -> None:
    """Elimina credenciales del usuario sin ningún proyecto asociado."""
    result = await db.execute(select(Integration).where(Integration.user_id == user_id))
    for integration in result.scalars().all():
        links = await db.execute(
            select(ProjectIntegration.id).where(
                ProjectIntegration.integration_id == integration.id
            )
        )
        if links.first() is None:
            await db.delete(integration)
    await db.commit()


async def get_project_jira_credentials(db: AsyncSession, project_id: str) -> dict | None:
    """{server, email, token} (descifrados) de la credencial Jira del proyecto."""
    integration = await get_project_integration(db, project_id)
    if not integration or integration.provider != "jira":
        return None
    secrets = await _secrets_for(db, integration.id)
    creds = {s.key_name: decrypt(s.encrypted_value) for s in secrets}
    if not all(k in creds for k in ("server", "email", "token")):
        return None
    return creds
