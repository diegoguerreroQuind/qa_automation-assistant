"""add_jira_tickets_table

Creates the jira_tickets table (full HU snapshots) and adds the
executions.jira_issue_id FK that links an execution to its Jira issue.

Revision ID: a1b2c3d4e5f6
Revises: 69fd0f899b08
Create Date: 2026-05-26 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '69fd0f899b08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jira_tickets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("issue_key", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("assignee", sa.String(length=255), nullable=True),
        sa.Column("reporter", sa.String(length=255), nullable=True),
        sa.Column("sprint", sa.String(length=255), nullable=True),
        sa.Column("story_points", sa.Float(), nullable=True),
        sa.Column("labels", sa.Text(), nullable=True),
        sa.Column("issue_type", sa.String(length=100), nullable=True),
        sa.Column("jira_created_at", sa.String(length=50), nullable=True),
        sa.Column("jira_updated_at", sa.String(length=50), nullable=True),
        sa.Column("raw_fields", sa.Text(), nullable=True),
        sa.Column("structured_criteria", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", "issue_key", name="uq_jira_user_issue"),
    )
    op.create_index("ix_jira_tickets_user_id", "jira_tickets", ["user_id"])
    op.create_index("ix_jira_tickets_issue_key", "jira_tickets", ["issue_key"])

    op.add_column(
        "executions",
        sa.Column("jira_issue_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_executions_jira_issue_id", "executions", ["jira_issue_id"])
    op.create_foreign_key(
        "fk_executions_jira_issue_id",
        "executions", "jira_tickets",
        ["jira_issue_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_executions_jira_issue_id", "executions", type_="foreignkey")
    op.drop_index("ix_executions_jira_issue_id", table_name="executions")
    op.drop_column("executions", "jira_issue_id")

    op.drop_index("ix_jira_tickets_issue_key", table_name="jira_tickets")
    op.drop_index("ix_jira_tickets_user_id", table_name="jira_tickets")
    op.drop_table("jira_tickets")
