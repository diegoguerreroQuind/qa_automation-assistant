from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_db
from backend.models.db import User
from backend.schemas.credentials import (
    CredentialUpsert, CredentialOut, CredentialGroup, CredentialDetail,
)
from backend.security.jwt import get_current_user
from backend.services.credentials_service import (
    upsert_credential, list_credentials, delete_credential,
)

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.put("", response_model=CredentialOut, status_code=status.HTTP_200_OK)
async def save_credential(
    body: CredentialUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Saves or updates a credential encrypted with AES-256-GCM (RNF-003).
    The raw value is NEVER logged or returned after this call.

    Examples:
    - provider=jira, key_name=token, value=<API token>
    - provider=jira, key_name=server, value=https://team.atlassian.net
    - provider=gemini, key_name=api_key, value=<Gemini API key>
    """
    cred = await upsert_credential(
        db=db,
        user_id=current_user.id,
        provider=body.provider,
        key_name=body.key_name,
        value=body.value,
    )
    return cred


@router.get("", response_model=list[CredentialGroup])
async def list_my_credentials(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a summary of stored credentials by provider.
    Secret values are NEVER included in the response.
    """
    creds = await list_credentials(db, current_user.id)
    groups: dict[str, list[str]] = defaultdict(list)
    for c in creds:
        groups[c.provider].append(c.key_name)
    return [
        CredentialGroup(provider=provider, keys=keys)
        for provider, keys in groups.items()
    ]


@router.get("/detailed", response_model=list[CredentialDetail])
async def list_my_credentials_detailed(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Per-credential metadata (id, provider, key_name, created/updated dates).
    Secret values are NEVER included. Used by the AI credentials management UI.
    """
    creds = await list_credentials(db, current_user.id)
    return creds


@router.delete("/{provider}/{key_name}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_credential(
    provider: str,
    key_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_credential(db, current_user.id, provider, key_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Credencial no encontrada")
