"""add_partial_execution_status

Revision ID: 69fd0f899b08
Revises: 5004fd173ba5
Create Date: 2026-05-26 20:21:20.049402

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69fd0f899b08'
down_revision: Union[str, Sequence[str], None] = '5004fd173ba5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """ExecutionStatus is stored as VARCHAR(20) in the DB — no DDL change needed.
    The 'partial' value is added to the Python enum only.
    This migration exists as a checkpoint in the version chain.
    """
    pass


def downgrade() -> None:
    pass
