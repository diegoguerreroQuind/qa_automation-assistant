import hashlib
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.models.database import get_db
from backend.models.db import User
from backend.services.redis_client import get_redis

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


# ---------------------------------------------------------------------------
# Token Revocation List (TRL) — backed by Redis
# A revoked token is stored with TTL = remaining token lifetime so Redis
# auto-expires the entry when the token would have expired anyway.
# ---------------------------------------------------------------------------

def _revocation_key(token: str) -> str:
    """
    Clave Redis para un token revocado. Se hashea el token (SHA-256) en lugar de
    almacenarlo en claro: si Redis se compromete, no se exponen JWTs válidos.
    """
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"revoked_token:{digest}"


def revoke_token(token: str, remaining_seconds: int) -> None:
    """Add a token to the Redis revocation list."""
    if remaining_seconds <= 0:
        return  # Already expired — nothing to revoke
    get_redis().setex(_revocation_key(token), remaining_seconds, "1")


def is_token_revoked(token: str) -> bool:
    """Return True if the token is in the Redis revocation list."""
    return get_redis().exists(_revocation_key(token)) > 0


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
    # Check revocation list AFTER successful decode (so we have the exp claim)
    if is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revocado. Por favor inicia sesión de nuevo.",
        )
    return payload


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(token)
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin usuario",
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )
    return user
