"""db hardening: tablas de integraciones faltantes + server defaults + ON DELETE

Mitiga riesgos detectados antes del despliegue inicial en Cloud SQL:

  1. La cadena de migraciones NO creaba las tablas de integraciones
     (integrations, integration_secrets, project_integrations). Existían en dev
     solo por create_all. Un `alembic upgrade head` limpio producía una BD
     incompleta. Aquí se crean (IF NOT EXISTS → idempotente en dev).
  2. Las columnas no tenían DEFAULT en la BD (los defaults vivían en la app), lo
     que rompía cualquier INSERT manual. Se fijan server defaults.
  3. Las FKs no tenían ON DELETE; las cascadas eran solo a nivel ORM. Se recrean
     con ON DELETE CASCADE (o SET NULL en executions.jira_issue_id) acorde a la
     intención del modelo.

Todo en SQL idempotente y offline-safe (IF [NOT] EXISTS, DROP CONSTRAINT IF
EXISTS), válido tanto sobre una BD de dev (create_all) como sobre una fresca.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-25 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabla, columna, ref_tabla, ref_col, accion)
_FKS = [
    ("projects", "user_id", "users", "id", "CASCADE"),
    ("credentials", "user_id", "users", "id", "CASCADE"),
    ("integrations", "user_id", "users", "id", "CASCADE"),
    ("jira_tickets", "user_id", "users", "id", "CASCADE"),
    ("jira_tickets", "project_id", "projects", "id", "CASCADE"),
    ("integration_secrets", "integration_id", "integrations", "id", "CASCADE"),
    ("project_integrations", "project_id", "projects", "id", "CASCADE"),
    ("project_integrations", "integration_id", "integrations", "id", "CASCADE"),
    ("executions", "project_id", "projects", "id", "CASCADE"),
    ("executions", "jira_issue_id", "jira_tickets", "id", "SET NULL"),
    ("endpoints", "execution_id", "executions", "id", "CASCADE"),
    ("generated_files", "execution_id", "executions", "id", "CASCADE"),
]

# Nombres alternativos a soltar (la cadena de migraciones nombró algunas FKs
# distinto a la convención por defecto de Postgres).
_FK_ALIASES = {
    ("executions", "jira_issue_id"): ["fk_executions_jira_issue_id"],
}

# (tabla, columna, expresion_default_sql)
_DEFAULTS = [
    ("users", "role", "'qa'"),
    ("users", "created_at", "now()"),
    ("projects", "created_at", "now()"),
    ("credentials", "created_at", "now()"),
    ("credentials", "updated_at", "now()"),
    ("integrations", "name", "''"),
    ("integrations", "created_at", "now()"),
    ("integrations", "updated_at", "now()"),
    ("jira_tickets", "fetched_at", "now()"),
    ("project_integrations", "created_at", "now()"),
    ("executions", "ai_model", "'gemini-pro-latest'"),
    ("executions", "status", "'pending'"),
    ("executions", "endpoints_total", "0"),
    ("executions", "endpoints_selected", "0"),
    ("executions", "endpoints_generated", "0"),
    ("executions", "created_at", "now()"),
    ("endpoints", "selected", "true"),
    ("endpoints", "status", "'pending'"),
    ("generated_files", "updated_at", "now()"),
]


def upgrade() -> None:
    # --- 1. Tablas de integraciones faltantes (idempotente) ------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS integrations (
            id VARCHAR(36) NOT NULL,
            user_id VARCHAR(36) NOT NULL,
            provider VARCHAR(20) NOT NULL,
            name VARCHAR(120) NOT NULL DEFAULT '',
            label VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_integrations_user_id ON integrations (user_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS integration_secrets (
            id SERIAL NOT NULL,
            integration_id VARCHAR(36) NOT NULL,
            key_name VARCHAR(50) NOT NULL,
            encrypted_value TEXT NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_integration_key UNIQUE (integration_id, key_name),
            FOREIGN KEY (integration_id) REFERENCES integrations (id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_integration_secrets_integration_id "
        "ON integration_secrets (integration_id)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS project_integrations (
            id SERIAL NOT NULL,
            project_id VARCHAR(36) NOT NULL,
            integration_id VARCHAR(36) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            CONSTRAINT uq_project_single_integration UNIQUE (project_id),
            FOREIGN KEY (project_id) REFERENCES projects (id),
            FOREIGN KEY (integration_id) REFERENCES integrations (id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_project_integrations_project_id "
        "ON project_integrations (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_project_integrations_integration_id "
        "ON project_integrations (integration_id)"
    )

    # --- 2. Server defaults (idempotente: SET DEFAULT se puede repetir) ------
    for table, column, default in _DEFAULTS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {default}")

    # credentials.updated_at: la migración histórica la creó NULLABLE, pero el
    # modelo la define NOT NULL. Backfill de nulos + enforce (converge el drift).
    op.execute("UPDATE credentials SET updated_at = now() WHERE updated_at IS NULL")
    op.execute("ALTER TABLE credentials ALTER COLUMN updated_at SET NOT NULL")

    # --- 3. FKs con ON DELETE (drop tolerante a nombres + add con acción) ----
    for table, column, ref_table, ref_col, action in _FKS:
        fk_name = f"{table}_{column}_fkey"
        names_to_drop = [fk_name] + _FK_ALIASES.get((table, column), [])
        for name in names_to_drop:
            op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {fk_name} "
            f"FOREIGN KEY ({column}) REFERENCES {ref_table} ({ref_col}) "
            f"ON DELETE {action}"
        )


def downgrade() -> None:
    # Revierte defaults y ON DELETE; NO elimina las tablas de integraciones
    # (pueden contener datos y su ausencia era un bug de la cadena, no un estado
    # deseado al que volver).
    for table, column, ref_table, ref_col, _action in _FKS:
        fk_name = f"{table}_{column}_fkey"
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {fk_name}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {fk_name} "
            f"FOREIGN KEY ({column}) REFERENCES {ref_table} ({ref_col})"
        )
    op.execute("ALTER TABLE credentials ALTER COLUMN updated_at DROP NOT NULL")
    for table, column, _default in _DEFAULTS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
