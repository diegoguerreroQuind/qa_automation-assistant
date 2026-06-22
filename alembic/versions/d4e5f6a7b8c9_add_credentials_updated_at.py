"""add_credentials_updated_at

Añade `credentials.updated_at` para mostrar fecha de actualización en la UI de
gestión de credenciales de IA. Backfill: updated_at = created_at en filas existentes.

Idempotente: usa information_schema para no fallar si la columna ya existe.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.first() is not None


def upgrade() -> None:
    if not _column_exists("credentials", "updated_at"):
        op.add_column(
            "credentials",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        # Backfill: las filas existentes heredan su fecha de creación.
        op.execute("UPDATE credentials SET updated_at = created_at WHERE updated_at IS NULL")


def downgrade() -> None:
    if _column_exists("credentials", "updated_at"):
        op.drop_column("credentials", "updated_at")
