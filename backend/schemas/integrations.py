from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

IntegrationProvider = Literal["jira", "azure"]


class ProjectRef(BaseModel):
    """Proyecto asociado a una credencial (para mostrar la relación)."""
    id: str
    name: str


class IntegrationCreate(BaseModel):
    """
    Crea una credencial y la asocia al proyecto. `values` son los pares
    clave/valor del proveedor (Jira: {server, email, token}); se cifran (AES-256).
    """
    name: str = Field(min_length=1, max_length=120)
    provider: IntegrationProvider
    values: dict[str, str] = Field(default_factory=dict)


class IntegrationTokenUpdate(BaseModel):
    """Renovación del token/PAT (único secreto editable)."""
    value: str = Field(min_length=1)


class LinkIntegrationRequest(BaseModel):
    integration_id: str


class IntegrationOut(BaseModel):
    """
    Vista segura de una credencial. NUNCA incluye valores secretos (token/pat);
    solo identidad (server, email…), estado, fechas y proyectos asociados.
    """
    id: str
    name: str
    provider: str
    label: str
    identity: dict[str, str] = Field(default_factory=dict)
    keys: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime
    projects: list[ProjectRef] = Field(default_factory=list)
