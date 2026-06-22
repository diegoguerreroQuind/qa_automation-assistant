import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String, Text, Boolean, Integer, Float, DateTime, ForeignKey,
    Enum as SAEnum, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    admin = "admin"
    qa = "qa"


class ExecutionStatus(str, enum.Enum):
    pending    = "pending"
    extracting = "extracting"
    generating = "generating"
    complete   = "complete"
    partial    = "partial"   # Generation finished but some endpoints failed
    failed     = "failed"


class EndpointStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    error = "error"


class CredentialProvider(str, enum.Enum):
    jira = "jira"
    azure = "azure"
    gemini = "gemini"
    claude = "claude"


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Timezone-aware UTC datetime (replaces deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.qa)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    projects: Mapped[list["Project"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    credentials: Mapped[list["Credential"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    integrations: Mapped[list["Integration"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Clave del proyecto Jira (ej. "EF") — se usa en el sync de HUs para filtrar
    # por proyecto en el JQL. Si es None, el sync buscará en todos los proyectos
    # a los que tenga acceso la credencial (comportamiento menos preciso).
    jira_project_key: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="projects")
    executions: Mapped[list["Execution"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    integration_links: Mapped[list["ProjectIntegration"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    jira_issues: Mapped[list["JiraIssue"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    jira_ticket_id: Mapped[str | None] = mapped_column(String(50))
    jira_ticket_summary: Mapped[str | None] = mapped_column(Text)
    # Reference to the full Jira issue record (description, metadata, criteria).
    # Nullable: executions can run without a linked Jira HU.
    jira_issue_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("jira_tickets.id"), index=True
    )
    ai_model: Mapped[str] = mapped_column(String(100), default="gemini-pro-latest")
    status: Mapped[str] = mapped_column(String(20), default=ExecutionStatus.pending)
    endpoints_total: Mapped[int] = mapped_column(Integer, default=0)
    endpoints_selected: Mapped[int] = mapped_column(Integer, default=0)
    endpoints_generated: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship(back_populates="executions")
    endpoints: Mapped[list["Endpoint"]] = relationship(back_populates="execution", cascade="all, delete-orphan")
    generated_files: Mapped[list["GeneratedFile"]] = relationship(back_populates="execution", cascade="all, delete-orphan")
    jira_issue: Mapped["JiraIssue | None"] = relationship(back_populates="executions")


class Endpoint(Base):
    __tablename__ = "endpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(36), ForeignKey("executions.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)  # URL original de Postman (con {{placeholders}})
    folder: Mapped[str | None] = mapped_column(String(255))
    selected: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default=EndpointStatus.pending)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Detalle del request (para la vista expandible de la UI). Se persiste en la
    # extracción para que el detalle sobreviva al borrado del directorio temporal.
    headers: Mapped[str | None] = mapped_column(Text)        # JSON {key: value}
    body: Mapped[str | None] = mapped_column(Text)           # body de ejemplo (raw)
    resolved_url: Mapped[str | None] = mapped_column(Text)   # URL con variables del Environment resueltas
    variables: Mapped[str | None] = mapped_column(Text)      # JSON {placeholder: valor_resuelto}

    execution: Mapped["Execution"] = relationship(back_populates="endpoints")


class GeneratedFile(Base):
    __tablename__ = "generated_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(36), ForeignKey("executions.id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20))  # gherkin | typescript | config
    file_content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    execution: Mapped["Execution"] = relationship(back_populates="generated_files")


class JiraIssue(Base):
    """
    Full snapshot of a Jira issue (HU) — stores the COMPLETE description and all
    metadata, not just an AI summary.

    Acts as a catalog of HUs per user (unique by user_id + issue_key) and is
    referenced by executions via Execution.jira_issue_id. Re-fetching the same
    ticket updates the existing row (upsert) so the data stays fresh.
    """
    __tablename__ = "jira_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # HU asociada a un proyecto (Proyecto → Credencial → Historias de Usuario).
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id"), index=True
    )

    # Core Jira fields
    issue_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)          # FULL description (Background, Scenarios, Criterios)

    # Metadata
    status: Mapped[str | None] = mapped_column(String(100))
    assignee: Mapped[str | None] = mapped_column(String(255))
    reporter: Mapped[str | None] = mapped_column(String(255))
    sprint: Mapped[str | None] = mapped_column(String(255))
    story_points: Mapped[float | None] = mapped_column(Float)
    labels: Mapped[str | None] = mapped_column(Text)              # comma-separated
    issue_type: Mapped[str | None] = mapped_column(String(100))
    jira_created_at: Mapped[str | None] = mapped_column(String(50))
    jira_updated_at: Mapped[str | None] = mapped_column(String(50))

    # Rich payloads (stored as JSON strings)
    raw_fields: Mapped[str | None] = mapped_column(Text)          # full Jira fields dump
    structured_criteria: Mapped[str | None] = mapped_column(Text) # AI-structured criteria per endpoint

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship()
    project: Mapped["Project | None"] = relationship(back_populates="jira_issues")
    executions: Mapped[list["Execution"]] = relationship(back_populates="jira_issue")

    # Una HU por (proyecto, issue_key): la misma HU puede existir de forma
    # independiente en distintos proyectos.
    __table_args__ = (
        UniqueConstraint("project_id", "issue_key", name="uq_jira_project_issue"),
    )


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # jira | azure | gemini | claude
    key_name: Mapped[str] = mapped_column(String(50), nullable=False)  # token | api_key | server_url
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="credentials")


# ---------------------------------------------------------------------------
# Integraciones (Jira / Azure DevOps / futuros conectores)
#
# Arquitectura: Usuario → Proyectos → Integraciones/Credenciales → HU.
# Una Integration es una credencial REUTILIZABLE del usuario (provider + label).
# Sus valores (server, email, token…) viven cifrados en IntegrationSecret.
# ProjectIntegration enlaza proyecto ↔ integración (muchos-a-muchos) para
# permitir reutilizar una misma credencial en varios proyectos.
# ---------------------------------------------------------------------------
class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # jira | azure
    # Nombre legible elegido por el usuario (identificador visible principal).
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="integrations")
    secrets: Mapped[list["IntegrationSecret"]] = relationship(
        back_populates="integration", cascade="all, delete-orphan"
    )
    project_links: Mapped[list["ProjectIntegration"]] = relationship(
        back_populates="integration", cascade="all, delete-orphan"
    )


class IntegrationSecret(Base):
    __tablename__ = "integration_secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    integration_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("integrations.id"), nullable=False, index=True
    )
    key_name: Mapped[str] = mapped_column(String(50), nullable=False)  # server | email | token …
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)

    integration: Mapped["Integration"] = relationship(back_populates="secrets")

    __table_args__ = (
        UniqueConstraint("integration_id", "key_name", name="uq_integration_key"),
    )


class ProjectIntegration(Base):
    __tablename__ = "project_integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    integration_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("integrations.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped["Project"] = relationship(back_populates="integration_links")
    integration: Mapped["Integration"] = relationship(back_populates="project_links")

    # Regla de negocio: un proyecto solo puede tener UNA credencial asociada
    # (una credencial sí puede estar en varios proyectos → relación 1:N).
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_single_integration"),
    )
