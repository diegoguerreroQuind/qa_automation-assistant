"""add_project_jira_key_and_jira_project_fk

Cambios:
  1. projects.jira_project_key (VARCHAR 50, nullable) — clave del proyecto Jira
     (ej. "EF") que se usa en el JQL al sincronizar HUs.
  2. jira_tickets.project_id (VARCHAR 36, nullable FK→projects.id) — asocia cada
     HU a un proyecto; índice + constraint de unicidad (project_id, issue_key).
     NOTA: la columna y sus índices ya fueron aplicados manualmente en la BD de
     desarrollo mediante ALTER TABLE. El upgrade() usa IF NOT EXISTS / try/except
     para ser idempotente (no falla si la columna ya existe).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Comprueba si una columna ya existe (idempotencia para ALTER ya aplicados)."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.first() is not None


def _index_exists(index_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :n"
        ),
        {"n": index_name},
    )
    return result.first() is not None


def _constraint_exists(constraint_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_constraint WHERE conname = :n"
        ),
        {"n": constraint_name},
    )
    return result.first() is not None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. projects.jira_project_key
    # -----------------------------------------------------------------------
    if not _column_exists("projects", "jira_project_key"):
        op.add_column(
            "projects",
            sa.Column("jira_project_key", sa.String(length=50), nullable=True),
        )

    # -----------------------------------------------------------------------
    # 2. jira_tickets.project_id  (puede estar ya presente por ALTER manual)
    # -----------------------------------------------------------------------
    if not _column_exists("jira_tickets", "project_id"):
        op.add_column(
            "jira_tickets",
            sa.Column("project_id", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            "jira_tickets_project_id_fkey",
            "jira_tickets", "projects",
            ["project_id"], ["id"],
            ondelete="CASCADE",
        )

    if not _index_exists("ix_jira_tickets_project_id"):
        op.create_index("ix_jira_tickets_project_id", "jira_tickets", ["project_id"])

    # -----------------------------------------------------------------------
    # 3. Cambiar la restricción única de (user_id, issue_key) →
    #    (project_id, issue_key) si aún no existe la nueva.
    # -----------------------------------------------------------------------
    if _constraint_exists("uq_jira_user_issue") and not _constraint_exists("uq_jira_project_issue"):
        op.drop_constraint("uq_jira_user_issue", "jira_tickets", type_="unique")
        op.create_unique_constraint(
            "uq_jira_project_issue", "jira_tickets", ["project_id", "issue_key"]
        )
    elif not _constraint_exists("uq_jira_project_issue"):
        op.create_unique_constraint(
            "uq_jira_project_issue", "jira_tickets", ["project_id", "issue_key"]
        )


def downgrade() -> None:
    # Revertir en orden inverso
    if _constraint_exists("uq_jira_project_issue"):
        op.drop_constraint("uq_jira_project_issue", "jira_tickets", type_="unique")

    if not _constraint_exists("uq_jira_user_issue"):
        op.create_unique_constraint(
            "uq_jira_user_issue", "jira_tickets", ["user_id", "issue_key"]
        )

    if _index_exists("ix_jira_tickets_project_id"):
        op.drop_index("ix_jira_tickets_project_id", table_name="jira_tickets")

    if _column_exists("jira_tickets", "project_id"):
        op.drop_constraint("jira_tickets_project_id_fkey", "jira_tickets", type_="foreignkey")
        op.drop_column("jira_tickets", "project_id")

    if _column_exists("projects", "jira_project_key"):
        op.drop_column("projects", "jira_project_key")
