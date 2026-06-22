"""role_column_to_enum_datetime_timezone

Revision ID: 5004fd173ba5
Revises: cf8b57388cb0
Create Date: 2026-05-26 19:57:12.494569

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5004fd173ba5'
down_revision: Union[str, Sequence[str], None] = 'cf8b57388cb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. DateTime columns: TIMESTAMP → TIMESTAMP WITH TIME ZONE
    for table, col, nullable in [
        ("credentials",    "created_at",  False),
        ("executions",     "created_at",  False),
        ("executions",     "completed_at", True),
        ("generated_files","updated_at",  False),
        ("projects",       "created_at",  False),
        ("users",          "created_at",  False),
    ]:
        op.alter_column(
            table, col,
            existing_type=postgresql.TIMESTAMP(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=nullable,
        )

    # 2. users.role: VARCHAR(20) → userrole ENUM
    #    PostgreSQL requires: CREATE TYPE first, then ALTER COLUMN with USING cast.
    userrole_enum = sa.Enum("admin", "qa", name="userrole")
    userrole_enum.create(op.get_bind(), checkfirst=True)
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE userrole "
        "USING role::text::userrole"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert users.role ENUM → VARCHAR(20)
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(20) USING role::text"
    )
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)

    # Revert DateTime(timezone=True) → TIMESTAMP (no timezone)
    for table, col, nullable in [
        ("users",          "created_at",  False),
        ("projects",       "created_at",  False),
        ("generated_files","updated_at",  False),
        ("executions",     "completed_at", True),
        ("executions",     "created_at",  False),
        ("credentials",    "created_at",  False),
    ]:
        op.alter_column(
            table, col,
            existing_type=sa.DateTime(timezone=True),
            type_=postgresql.TIMESTAMP(),
            existing_nullable=nullable,
        )
