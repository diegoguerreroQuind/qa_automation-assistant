from datetime import datetime

from pydantic import BaseModel


class CredentialUpsert(BaseModel):
    provider: str   # jira | azure | gemini | claude
    key_name: str   # token | api_key | server_url | email
    value: str      # raw value — encrypted at service layer


class CredentialOut(BaseModel):
    id: int
    provider: str
    key_name: str
    # NOTE: encrypted_value is NEVER returned to the client

    model_config = {"from_attributes": True}


class CredentialGroup(BaseModel):
    """Summary of stored credentials by provider (no secret values)."""
    provider: str
    keys: list[str]


class CredentialDetail(BaseModel):
    """
    Per-credential metadata for the management UI (no secret values).
    Used to render the AI credentials list with provider + created/updated dates.
    """
    id: int
    provider: str
    key_name: str
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
