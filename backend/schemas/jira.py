from datetime import datetime

from pydantic import BaseModel, Field


class JiraCredentials(BaseModel):
    """Reusable base for any request that needs Jira credentials."""
    server: str
    email: str
    token: str


class JiraQueryBody(JiraCredentials):
    """Request body for listing/filtering Jira tickets."""
    project_key: str | None = None
    statuses: list[str] = Field(
        default=["En curso", "En certificación"],
        min_length=1,
        description=(
            "Al menos 1 estado requerido. Se usa para construir el JQL: "
            "status IN ('En curso', 'En certificación')"
        ),
    )


class JiraTicket(BaseModel):
    """
    Full Jira issue representation returned by the API.

    `raw` carries the complete Jira fields payload for persistence; it is
    excluded from API responses (exclude=True) to keep payloads small.
    """
    key: str
    summary: str
    status: str
    assignee: str | None = None
    reporter: str | None = None
    sprint: str | None = None
    story_points: float | None = None
    labels: list[str] = Field(default_factory=list)
    issue_type: str | None = None
    description: str | None = None
    created: str | None = None
    updated: str | None = None
    raw: dict | None = Field(default=None, exclude=True)


class JiraTicketsResponse(BaseModel):
    """
    Enriched response for the ticket listing endpoint.

    Returning total + filters alongside the list lets the frontend
    distinguish "0 tickets matching your filters" from an API error.
    """
    tickets: list[JiraTicket]
    total: int
    filters: dict


# ---------------------------------------------------------------------------
# Schemas that read credentials from the encrypted DB table.
# Use these instead of JiraQueryBody when the user has already saved their
# Jira credentials via PUT /credentials.
# ---------------------------------------------------------------------------

class JiraQueryBodyFromDB(BaseModel):
    """
    Request body for ticket listing when credentials are stored in the DB.
    No Jira credentials needed — they are read from the credentials table.

    Defaults replicate the board's "En curso" column: statusCategory
    'In Progress' within active sprints, regardless of assignee.
    """
    project_key: str | None = Field(
        default=None,
        description="Clave del proyecto, ej. 'EF'. Recomendado para acotar resultados.",
    )
    status_categories: list[str] = Field(
        default=["In Progress"],
        description=(
            "Categorías de estado (columnas del tablero): 'To Do', 'In Progress', 'Done'. "
            "Robusto frente a nombres de estado duplicados entre workflows."
        ),
    )
    statuses: list[str] | None = Field(
        default=None,
        description=(
            "Opcional. Nombres exactos de estado. Si se envía, tiene prioridad "
            "sobre status_categories (úsalo solo si conoces el id/nombre único)."
        ),
    )
    only_mine: bool = Field(
        default=False,
        description="Si es true, solo HUs asignadas a ti. Por defecto trae todas.",
    )
    only_open_sprints: bool = Field(
        default=True,
        description="Si es true, solo HUs en sprints activos.",
    )


# ---------------------------------------------------------------------------
# Schemas for reading persisted Jira issues (HUs) from the local DB.
# Used by GET /jira/tickets — does NOT call Jira, returns what was already saved.
# ---------------------------------------------------------------------------

class JiraIssueStored(BaseModel):
    """A full Jira issue (HU) snapshot as stored in the jira_tickets table."""
    id: str
    issue_key: str
    summary: str
    description: str | None
    status: str | None
    assignee: str | None
    reporter: str | None
    sprint: str | None
    story_points: float | None
    labels: str | None
    issue_type: str | None
    jira_created_at: str | None
    jira_updated_at: str | None
    fetched_at: datetime

    model_config = {"from_attributes": True}


class JiraIssuesStoredResponse(BaseModel):
    """Listing of persisted HUs for the authenticated user."""
    tickets: list[JiraIssueStored]
    total: int
