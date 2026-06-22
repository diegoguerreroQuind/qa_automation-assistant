from __future__ import annotations
import json
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Postgres variables individuales (para compatibilidad con Postgres.app) ──
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_db: str = "qa_assistant"

    # ── DATABASE_URL: si está seteada en .env la usa directamente;
    #    si no, la construye desde las variables individuales ──
    database_url: str = ""

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.database_url and self.postgres_user:
            if self.postgres_password:
                auth = f"{self.postgres_user}:{self.postgres_password}"
            else:
                auth = self.postgres_user
            self.database_url = (
                f"postgresql+asyncpg://{auth}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self

    # ── Redis / Celery ──
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── IA — Gemini ──
    google_api_key: str = ""

    # ── Seguridad ──
    secret_key: str = Field(
        ...,
        description=(
            "Requerido. Genera una con: "
            "python3 -c \"import secrets; print(secrets.token_hex(32))\""
        ),
    )
    encryption_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 12

    # ── CORS ──
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Frontend (destino de la redirección tras el callback OAuth) ──
    frontend_url: str = "http://localhost:5173"

    # ── Sesiones temporales ──
    sessions_base_dir: str = "/tmp/qa-sessions"
    session_ttl_hours: int = 48

    # ── OAuth Google (SSO) ──
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    # ── OAuth Jira / Atlassian (SSO) ──
    jira_client_id: str = ""
    jira_client_secret: str = ""
    jira_redirect_uri: str = "http://localhost:8000/auth/jira/callback"

    # ── SSL corporativo ──
    disable_ssl_verify: bool = False

    environment: str = "development"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if v and len(bytes.fromhex(v)) != 32:
            raise ValueError("ENCRYPTION_KEY debe ser exactamente 32 bytes (64 caracteres hex)")
        return v

    @property
    def encryption_key_bytes(self) -> bytes:
        if not self.encryption_key:
            raise RuntimeError(
                "ENCRYPTION_KEY no está configurada en .env. "
                "Genera una con: python3 -c \"import secrets; print(secrets.token_bytes(32).hex())\""
            )
        return bytes.fromhex(self.encryption_key)

    @property
    def sync_database_url(self) -> str:
        """URL sincrónica para Alembic y Celery (psycopg2)."""
        return (
            self.database_url
            .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
            .replace("sqlite+aiosqlite://", "sqlite://")
        )


settings = Settings()
