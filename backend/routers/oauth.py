"""
SSO via OAuth2 (Authorization Code flow) para Google y Jira/Atlassian.

Flujo:
  1. El navegador va a  GET /auth/{provider}/login
     → redirige al proveedor con un `state` firmado (anti-CSRF).
  2. El proveedor regresa a  GET /auth/{provider}/callback?code&state
     → se intercambia el code por un access_token, se obtiene el email/nombre,
       se hace upsert del usuario y se emite NUESTRO JWT.
     → redirige al frontend:  {FRONTEND_URL}/auth/callback?token=<jwt>
       (o ?error=<motivo> si algo falla).

Azure DevOps se implementará más adelante.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.database import get_db
from backend.models.db import User, UserRole
from backend.security.jwt import create_access_token

logger = logging.getLogger("qa_assistant.oauth")

router = APIRouter(prefix="/auth", tags=["oauth"])

STATE_TTL_SECONDS = 600  # 10 minutos para completar el flujo


# ---------------------------------------------------------------------------
# Metadatos por proveedor. Las credenciales se leen de settings en cada
# request (no se "congelan" al importar el módulo).
# ---------------------------------------------------------------------------
def _provider_config(provider: str) -> dict | None:
    if provider == "google":
        return {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
            "scope": "openid email profile",
            "extra_authorize": {"access_type": "online", "prompt": "select_account"},
            "token_style": "form",
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
        }
    if provider == "jira":
        return {
            "authorize_url": "https://auth.atlassian.com/authorize",
            "token_url": "https://auth.atlassian.com/oauth/token",
            "userinfo_url": "https://api.atlassian.com/me",
            "scope": "read:me",
            "extra_authorize": {"audience": "api.atlassian.com", "prompt": "consent"},
            "token_style": "json",
            "client_id": settings.jira_client_id,
            "client_secret": settings.jira_client_secret,
            "redirect_uri": settings.jira_redirect_uri,
        }
    return None


def _is_configured(cfg: dict) -> bool:
    return bool(cfg["client_id"] and cfg["client_secret"])


def _sign_state(provider: str) -> str:
    payload = {
        "provider": provider,
        "nonce": secrets.token_urlsafe(16),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=STATE_TTL_SECONDS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _verify_state(state: str, provider: str) -> bool:
    try:
        payload = jwt.decode(state, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return False
    return payload.get("provider") == provider


def _frontend_redirect(*, token: str | None = None, error: str | None = None) -> RedirectResponse:
    params = {"token": token} if token else {"error": error or "oauth_failed"}
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?{urlencode(params)}")


# ---------------------------------------------------------------------------
# 1) Inicio del flujo → redirige al proveedor
# ---------------------------------------------------------------------------
@router.get("/{provider}/login")
async def oauth_login(provider: str):
    cfg = _provider_config(provider)
    if cfg is None:
        return _frontend_redirect(error="unsupported_provider")
    if not _is_configured(cfg):
        logger.warning("OAuth %s solicitado pero sin credenciales configuradas", provider)
        return _frontend_redirect(error="provider_not_configured")

    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": cfg["scope"],
        "state": _sign_state(provider),
        **cfg["extra_authorize"],
    }
    return RedirectResponse(f"{cfg['authorize_url']}?{urlencode(params)}")


# ---------------------------------------------------------------------------
# 2) Callback → intercambia code, obtiene identidad, emite JWT propio
# ---------------------------------------------------------------------------
@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    cfg = _provider_config(provider)
    if cfg is None:
        return _frontend_redirect(error="unsupported_provider")
    if error:
        return _frontend_redirect(error=error)
    if not code or not state or not _verify_state(state, provider):
        return _frontend_redirect(error="invalid_state")

    verify = not settings.disable_ssl_verify
    try:
        async with httpx.AsyncClient(timeout=15, verify=verify) as client:
            access_token = await _exchange_code(client, cfg, code)
            email, name = await _fetch_identity(client, cfg, access_token)
    except Exception as exc:  # noqa: BLE001 — cualquier fallo de red/proveedor
        logger.error("OAuth %s callback falló: %s", provider, exc, exc_info=True)
        return _frontend_redirect(error="oauth_exchange_failed")

    if not email:
        return _frontend_redirect(error="email_not_available")

    user = await _upsert_oauth_user(db, email=email, name=name or email.split("@")[0])
    jwt_token = create_access_token(user.id, user.email)
    logger.info("OAuth %s OK para %s", provider, email)
    return _frontend_redirect(token=jwt_token)


# ---------------------------------------------------------------------------
# Helpers de red
# ---------------------------------------------------------------------------
async def _exchange_code(client: httpx.AsyncClient, cfg: dict, code: str) -> str:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "redirect_uri": cfg["redirect_uri"],
    }
    if cfg["token_style"] == "json":
        resp = await client.post(cfg["token_url"], json=data)
    else:
        resp = await client.post(cfg["token_url"], data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]


async def _fetch_identity(
    client: httpx.AsyncClient, cfg: dict, access_token: str
) -> tuple[str | None, str | None]:
    resp = await client.get(
        cfg["userinfo_url"], headers={"Authorization": f"Bearer {access_token}"}
    )
    resp.raise_for_status()
    info = resp.json()
    # Google → {email, name}; Atlassian → {email, name, account_id}
    return info.get("email"), info.get("name")


async def _upsert_oauth_user(db: AsyncSession, *, email: str, name: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=email, name=name, hashed_password=None, role=UserRole.qa)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user
