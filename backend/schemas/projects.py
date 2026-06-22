from datetime import datetime
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    jira_project_key: str | None = Field(
        default=None,
        description="Clave del proyecto Jira (ej. 'EF'). Requerida para sincronizar HUs.",
    )


class ProjectUpdate(BaseModel):
    name: str
    description: str | None = None
    jira_project_key: str | None = Field(
        default=None,
        description="Clave del proyecto Jira (ej. 'EF'). Requerida para sincronizar HUs.",
    )


class CredentialRef(BaseModel):
    """Credencial asociada a un proyecto (resumen para la UI)."""
    id: str
    name: str
    provider: str


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    jira_project_key: str | None = None
    created_at: datetime
    credential: CredentialRef | None = None

    model_config = {"from_attributes": True}


class ExecutionSummary(BaseModel):
    id: str
    project_id: str
    jira_ticket_id: str | None
    jira_ticket_summary: str | None
    ai_model: str
    status: str
    endpoints_total: int
    endpoints_selected: int
    endpoints_generated: int
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
