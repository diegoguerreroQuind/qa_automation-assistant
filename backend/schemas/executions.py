import json
from typing import Literal
from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
class ExecutionCreate(BaseModel):
    project_id: str
    jira_ticket_id: str | None = None
    ai_model: Literal[
        "gemini-pro-latest",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ] = "gemini-pro-latest"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
class EndpointOut(BaseModel):
    id: int
    name: str
    method: str
    url: str                       # URL original de Postman (con {{placeholders}})
    folder: str | None
    selected: bool
    status: str
    error_message: str | None = None

    # Detalle para la vista expandible (RF-002). headers/variables se almacenan
    # como JSON en la BD; los validadores los deserializan a dict.
    headers: dict[str, str] = {}
    body: str | None = None
    resolved_url: str | None = None
    variables: dict[str, str] = {}

    model_config = {"from_attributes": True}

    @field_validator("headers", "variables", mode="before")
    @classmethod
    def _parse_json(cls, value):
        """Deserializa la columna Text (JSON) a dict; tolera None/str/dict."""
        if value is None or value == "":
            return {}
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except (ValueError, TypeError):
                return {}
        return value


class EndpointSelectionUpdate(BaseModel):
    selected_ids: list[int]


# ---------------------------------------------------------------------------
# Jira fetch (step 4 of pipeline)
# ---------------------------------------------------------------------------
class FetchJiraRequest(BaseModel):
    """
    Credentials (server, email, token) are read from the encrypted credentials
    table — not passed here. Store them first via PUT /credentials.
    """
    issue_key: str


class FetchJiraResponse(BaseModel):
    issue_key: str
    context_ready: bool
    endpoints_with_criteria: int
    business_summary: str


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
class GenerateRequest(BaseModel):
    """
    No Jira credentials here — the Celery worker reads them directly from the
    encrypted credentials table (AES-256-GCM) to keep tokens out of Redis.
    """
    pass


class GenerationJobResponse(BaseModel):
    job_id: str
    status: str
    execution_id: str


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
class FileOut(BaseModel):
    id: int
    file_name: str
    file_type: str
    file_content: str

    model_config = {"from_attributes": True}


class FileUpdate(BaseModel):
    content: str
