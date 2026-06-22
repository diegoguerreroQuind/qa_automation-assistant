"""add_endpoint_detail_columns

Añade a la tabla `endpoints` el detalle del request para la vista expandible
del módulo Ejecuciones (RF-002):

  - headers       (TEXT, JSON {key: value})
  - body          (TEXT, body de ejemplo raw)
  - resolved_url  (TEXT, URL con variables del Environment resueltas)
  - variables     (TEXT, JSON {placeholder: valor_resuelto})

Idempotente: usa information_schema para no fallar si las columnas ya existen.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_COLUMNS = ("headers", "body", "resolved_url", "variables")


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
    for column in _NEW_COLUMNS:
        if not _column_exists("endpoints", column):
            op.add_column("endpoints", sa.Column(column, sa.Text(), nullable=True))


def downgrade() -> None:
    for column in reversed(_NEW_COLUMNS):
        if _column_exists("endpoints", column):
            op.drop_column("endpoints", column)
