"""
Persistence layer for full Jira issue (HU) snapshots.

Stores the COMPLETE Jira issue in the jira_tickets table — full description,
metadata and (optionally) the AI-structured acceptance criteria — so the data
survives the 48h session cleanup that wipes inputContext.json from disk.

Upsert keyed by (user_id, issue_key): re-fetching the same ticket refreshes
the existing row instead of duplicating it.
"""
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import JiraIssue
from backend.schemas.jira import JiraTicket


async def upsert_jira_issue(
    db: AsyncSession,
    user_id: str,
    ticket: JiraTicket,
    structured_criteria: dict | None = None,
) -> JiraIssue:
    """
    Creates or updates the full JiraIssue record for (user_id, issue_key).

    Args:
        db:                   Async DB session.
        user_id:              Owner of the snapshot.
        ticket:               Enriched JiraTicket from JiraService (includes raw).
        structured_criteria:  Optional AI-structured criteria dict to persist
                              (only set during the fetch-jira generation flow).

    Returns:
        The persisted JiraIssue ORM object.
    """
    result = await db.execute(
        select(JiraIssue).where(
            JiraIssue.user_id == user_id,
            JiraIssue.issue_key == ticket.key,
        )
    )
    issue = result.scalar_one_or_none()

    labels_str = ", ".join(ticket.labels) if ticket.labels else None
    raw_str = json.dumps(ticket.raw, ensure_ascii=False, default=str) if ticket.raw else None
    criteria_str = (
        json.dumps(structured_criteria, ensure_ascii=False)
        if structured_criteria is not None
        else None
    )

    if issue:
        issue.summary = ticket.summary
        issue.description = ticket.description
        issue.status = ticket.status
        issue.assignee = ticket.assignee
        issue.reporter = ticket.reporter
        issue.sprint = ticket.sprint
        issue.story_points = ticket.story_points
        issue.labels = labels_str
        issue.issue_type = ticket.issue_type
        issue.jira_created_at = ticket.created
        issue.jira_updated_at = ticket.updated
        issue.raw_fields = raw_str
        # Only overwrite criteria when new ones are provided
        if criteria_str is not None:
            issue.structured_criteria = criteria_str
    else:
        issue = JiraIssue(
            user_id=user_id,
            issue_key=ticket.key,
            summary=ticket.summary,
            description=ticket.description,
            status=ticket.status,
            assignee=ticket.assignee,
            reporter=ticket.reporter,
            sprint=ticket.sprint,
            story_points=ticket.story_points,
            labels=labels_str,
            issue_type=ticket.issue_type,
            jira_created_at=ticket.created,
            jira_updated_at=ticket.updated,
            raw_fields=raw_str,
            structured_criteria=criteria_str,
        )
        db.add(issue)

    await db.commit()
    await db.refresh(issue)
    return issue


async def upsert_project_jira_issue(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    ticket: JiraTicket,
) -> JiraIssue:
    """
    Upsert de una HU asociada a un proyecto, keyed by (project_id, issue_key).
    Cada proyecto mantiene su propio repositorio de Historias de Usuario.
    """
    result = await db.execute(
        select(JiraIssue).where(
            JiraIssue.project_id == project_id,
            JiraIssue.issue_key == ticket.key,
        )
    )
    issue = result.scalar_one_or_none()

    labels_str = ", ".join(ticket.labels) if ticket.labels else None
    raw_str = json.dumps(ticket.raw, ensure_ascii=False, default=str) if ticket.raw else None

    if issue:
        issue.summary = ticket.summary
        issue.description = ticket.description
        issue.status = ticket.status
        issue.assignee = ticket.assignee
        issue.reporter = ticket.reporter
        issue.sprint = ticket.sprint
        issue.story_points = ticket.story_points
        issue.labels = labels_str
        issue.issue_type = ticket.issue_type
        issue.jira_created_at = ticket.created
        issue.jira_updated_at = ticket.updated
        issue.raw_fields = raw_str
    else:
        issue = JiraIssue(
            user_id=user_id,
            project_id=project_id,
            issue_key=ticket.key,
            summary=ticket.summary,
            description=ticket.description,
            status=ticket.status,
            assignee=ticket.assignee,
            reporter=ticket.reporter,
            sprint=ticket.sprint,
            story_points=ticket.story_points,
            labels=labels_str,
            issue_type=ticket.issue_type,
            jira_created_at=ticket.created,
            jira_updated_at=ticket.updated,
            raw_fields=raw_str,
        )
        db.add(issue)

    await db.commit()
    await db.refresh(issue)
    return issue
