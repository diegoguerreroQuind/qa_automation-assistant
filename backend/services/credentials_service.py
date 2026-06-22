"""
Service layer for encrypted credential storage (RNF-003).

Credentials (Jira tokens, AI API keys) are encrypted with AES-256-GCM
before being written to the database. The master key lives exclusively
in the ENCRYPTION_KEY environment variable — never in the DB.

Two variants are provided:
- Async functions (upsert_credential, get_credential, list_credentials, delete_credential)
  for use in FastAPI async route handlers.
- Synchronous function (get_credential_sync) for use in Celery workers, which cannot
  use asyncio event loops.
"""
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.db import Credential
from backend.security.encryption import encrypt, decrypt


async def upsert_credential(
    db: AsyncSession,
    user_id: str,
    provider: str,
    key_name: str,
    value: str,
) -> Credential:
    """Creates or updates a credential. Value is AES-256-GCM encrypted."""
    result = await db.execute(
        select(Credential).where(
            Credential.user_id == user_id,
            Credential.provider == provider,
            Credential.key_name == key_name,
        )
    )
    cred = result.scalar_one_or_none()

    encrypted = encrypt(value)
    if cred:
        cred.encrypted_value = encrypted
    else:
        cred = Credential(
            user_id=user_id,
            provider=provider,
            key_name=key_name,
            encrypted_value=encrypted,
        )
        db.add(cred)

    await db.commit()
    await db.refresh(cred)
    return cred


async def get_credential(
    db: AsyncSession,
    user_id: str,
    provider: str,
    key_name: str,
) -> str | None:
    """Returns the decrypted value of a stored credential, or None."""
    result = await db.execute(
        select(Credential).where(
            Credential.user_id == user_id,
            Credential.provider == provider,
            Credential.key_name == key_name,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        return None
    return decrypt(cred.encrypted_value)


async def list_credentials(
    db: AsyncSession,
    user_id: str,
) -> list[Credential]:
    """Returns all credential records for a user (without decrypting values)."""
    result = await db.execute(
        select(Credential).where(Credential.user_id == user_id)
    )
    return result.scalars().all()


async def delete_credential(
    db: AsyncSession,
    user_id: str,
    provider: str,
    key_name: str,
) -> bool:
    result = await db.execute(
        select(Credential).where(
            Credential.user_id == user_id,
            Credential.provider == provider,
            Credential.key_name == key_name,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        return False
    await db.delete(cred)
    await db.commit()
    return True


def get_credential_sync(
    engine,
    user_id: str,
    provider: str,
    key_name: str,
) -> str | None:
    """
    Synchronous credential lookup for Celery workers.

    Celery tasks cannot use asyncio event loops, so this function uses a
    plain SQLAlchemy synchronous Session instead of AsyncSession.
    The returned value is already decrypted.
    """
    from sqlalchemy.orm import Session
    from backend.security.encryption import decrypt

    with Session(engine) as db:
        cred = db.execute(
            select(Credential).where(
                Credential.user_id == user_id,
                Credential.provider == provider,
                Credential.key_name == key_name,
            )
        ).scalar_one_or_none()
        if not cred:
            return None
        return decrypt(cred.encrypted_value)
