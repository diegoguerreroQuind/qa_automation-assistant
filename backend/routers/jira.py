import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.db import User, JiraIssue
from backend.schemas.jira import (
    JiraQueryBodyFromDB,
    JiraTicket,
    JiraTicketsResponse,
    JiraIssueStored,
    JiraIssuesStoredResponse,
)
from backend.security.jwt import get_current_user
from backend.services.credentials_service import get_credential
from backend.services.jira_service import JiraService
from backend.services.jira_persistence import upsert_jira_issue

router = APIRouter(prefix="/jira", tags=["jira"])
logger = logging.getLogger("qa_assistant.jira")

# Mensaje genérico al cliente; el detalle crudo de Jira (que puede incluir URLs
# internas o trazas) se registra solo en el log del servidor.
_JIRA_QUERY_FAILED = "No se pudo consultar Jira. Revisa las credenciales e inténtalo de nuevo."

_JIRA_CREDS_MISSING = (
    "Credenciales Jira no configuradas. "
    "Guárdalas primero en PUT /credentials "
    "(provider='jira', keys: server / email / token)."
)


async def _get_jira_service(user_id: str, db: AsyncSession) -> JiraService:
    """Reads Jira credentials from the encrypted DB table and returns a JiraService."""
    server = await get_credential(db, user_id, "jira", "server")
    email  = await get_credential(db, user_id, "jira", "email")
    token  = await get_credential(db, user_id, "jira", "token")

    if not server or not email or not token:
        raise HTTPException(status_code=424, detail=_JIRA_CREDS_MISSING)

    return JiraService(server=server, email=email, token=token)


@router.post(
    "/tickets",
    response_model=JiraTicketsResponse,
    summary="Lista tickets filtrados de Jira",
    responses={424: {"description": "Credenciales Jira no guardadas en la BD"}},
)
async def list_tickets(
    body: JiraQueryBodyFromDB,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns Jira tickets filtered by:
    - Assigned to the authenticated user
    - In active sprint
    - Status in ["En curso", "En certificación"] (configurable via `statuses`)

    Credentials are read from the encrypted credentials table.
    Store them first via PUT /credentials.

    Response includes `total` and `filters` so the frontend can distinguish
    "0 tickets matching these filters" from a Jira connectivity error.
    """
    service = await _get_jira_service(current_user.id, db)

    assignee_email = None
    if body.only_mine:
        assignee_email = await get_credential(db, current_user.id, "jira", "email")

    try:
        tickets = service.get_filtered_tickets(
            project_key=body.project_key,
            status_categories=body.status_categories,
            statuses=body.statuses,
            assignee_email=assignee_email,
            only_open_sprints=body.only_open_sprints,
        )
        # Persist the full HU snapshot for every listed ticket
        for ticket in tickets:
            await upsert_jira_issue(db, current_user.id, ticket)

        return JiraTicketsResponse(
            tickets=tickets,
            total=len(tickets),
            filters={
                "project_key": body.project_key,
                "status_categories": body.status_categories,
                "statuses": body.statuses,
                "only_mine": body.only_mine,
                "only_open_sprints": body.only_open_sprints,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error consultando Jira: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=_JIRA_QUERY_FAILED)


@router.get(
    "/tickets",
    response_model=JiraIssuesStoredResponse,
    summary="Lista las HUs ya guardadas en la BD (sin llamar a Jira)",
)
async def list_stored_tickets(
    status: str | None = Query(
        None, description="Filtra por estado exacto, ej. 'En curso'"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the full HU snapshots already persisted for the authenticated user.

    Does NOT call Jira — reads from the jira_tickets table. Use this to render
    the catalog of HUs in the frontend (descripción completa + metadatos).
    Populate the catalog first with POST /jira/tickets.
    """
    stmt = select(JiraIssue).where(JiraIssue.user_id == current_user.id)
    if status:
        stmt = stmt.where(JiraIssue.status == status)
    stmt = stmt.order_by(JiraIssue.fetched_at.desc())

    rows = (await db.execute(stmt)).scalars().all()
    return JiraIssuesStoredResponse(
        tickets=[JiraIssueStored.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post(
    "/tickets/{issue_key}",
    response_model=JiraTicket,
    summary="Detalle de un ticket Jira",
    responses={424: {"description": "Credenciales Jira no guardadas en la BD"}},
)
async def get_ticket_detail(
    issue_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns full details of a specific Jira issue.
    Credentials are read from the encrypted credentials table.
    """
    service = await _get_jira_service(current_user.id, db)
    try:
        ticket = service.get_ticket_detail(issue_key)
        await upsert_jira_issue(db, current_user.id, ticket)
        return ticket
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error consultando Jira: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=_JIRA_QUERY_FAILED)
