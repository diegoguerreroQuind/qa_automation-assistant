"""
Service layer for Execution business logic.

Moves DB orchestration out of routers so handlers stay thin.
"""
import json
import logging
from dataclasses import dataclass

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from backend.core.state_machine import assert_valid_transition, InvalidStatusTransitionError
from backend.models.db import Endpoint, Execution, ExecutionStatus
from backend.repositories import execution_repository as execution_repo
from backend.services.credentials_service import get_credential
from backend.services.jira_persistence import upsert_jira_issue
from backend.services.jira_service import JiraService

logger = logging.getLogger("qa_assistant.execution_service")


# ---------------------------------------------------------------------------
# Errores de dominio del caso de uso fetch-jira (el router los traduce a HTTP)
# ---------------------------------------------------------------------------
class FetchJiraError(Exception):
    """Base de errores del caso de uso fetch-jira."""


class JiraCredentialsMissing(FetchJiraError):
    """No hay credenciales Jira guardadas para el usuario."""


class NoEndpointsExtracted(FetchJiraError):
    """La ejecución no tiene endpoints (falta el paso de extracción)."""


class JiraContextFetchFailed(FetchJiraError):
    """Falló la consulta a Jira / estructuración por IA."""


@dataclass
class FetchJiraResult:
    issue_key: str
    endpoints_with_criteria: int
    business_summary: str


async def save_extracted_endpoints(
    db: AsyncSession,
    execution_id: str,
    endpoints_data: list[dict],
) -> list[Endpoint]:
    """
    Idempotently persists extracted endpoints for an execution.

    - Validates the state transition (must be pending/extracting/failed → extracting).
    - Deletes any previously stored endpoints (re-extract is safe).
    - Inserts new Endpoint rows with selected=True by default.
    - Updates Execution status to 'extracting' with totals.

    Returns the freshly inserted Endpoint ORM objects.
    """
    # Read current status to validate transition before writing anything
    exec_result = await db.execute(
        select(Execution.status).where(Execution.id == execution_id)
    )
    current_status = exec_result.scalar_one_or_none()
    if current_status is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")

    try:
        assert_valid_transition(current_status, ExecutionStatus.extracting)
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Wipe previous extraction so re-calls are idempotent
    await db.execute(
        delete(Endpoint).where(Endpoint.execution_id == execution_id)
    )

    for ep in endpoints_data:
        headers = ep.get("headers") or {}
        variables = ep.get("variables") or {}
        db.add(Endpoint(
            execution_id=execution_id,
            name=(
                ep.get("nombre_peticion")
                or ep.get("nombre")
                or ep.get("name")
                or "unknown"
            ),
            method=ep.get("metodo") or ep.get("method") or "GET",
            url=str(ep.get("url", "")),
            folder=ep.get("ruta_carpeta") or ep.get("carpeta") or ep.get("folder"),
            selected=True,
            # Detalle para la vista expandible de la UI (RF-002).
            headers=json.dumps(headers, ensure_ascii=False) if headers else None,
            body=ep.get("body"),
            resolved_url=ep.get("url_resuelta") or ep.get("resolved_url") or None,
            variables=json.dumps(variables, ensure_ascii=False) if variables else None,
        ))

    await db.execute(
        update(Execution)
        .where(Execution.id == execution_id)
        .values(
            status=ExecutionStatus.extracting,
            endpoints_total=len(endpoints_data),
            endpoints_selected=len(endpoints_data),
        )
    )
    await db.commit()

    result = await db.execute(
        select(Endpoint).where(Endpoint.execution_id == execution_id)
    )
    return result.scalars().all()


async def fetch_and_link_jira_context(
    db: AsyncSession,
    *,
    execution_id: str,
    user_id: str,
    issue_key: str,
) -> FetchJiraResult:
    """
    Caso de uso: dada una ejecución con endpoints extraídos, consulta la HU en
    Jira, estructura sus criterios de aceptación con IA contra esos endpoints,
    persiste el snapshot completo de la HU y vincula todo a la ejecución.

    Orquestación pura (sin HTTP): señala los fallos con excepciones de dominio
    (JiraCredentialsMissing / NoEndpointsExtracted / JiraContextFetchFailed) que
    el router traduce a códigos HTTP. La ownership la valida el router antes.
    """
    server = await get_credential(db, user_id, "jira", "server")
    email = await get_credential(db, user_id, "jira", "email")
    token = await get_credential(db, user_id, "jira", "token")
    if not server or not email or not token:
        raise JiraCredentialsMissing()

    # Los nombres de endpoint vienen de la BD (fuente durable) para anclar los
    # criterios a los nombres EXACTOS de Postman aunque /tmp se haya purgado.
    ep_rows = await execution_repo.list_endpoints(db, execution_id)
    if not ep_rows:
        raise NoEndpointsExtracted()

    endpoints_for_ai = [
        {"nombre_peticion": ep.name, "metodo": ep.method, "url": ep.url} for ep in ep_rows
    ]

    # Import diferido: pipeline_service arrastra el core de generación (app/).
    from backend.services.pipeline_service import fetch_jira_context

    try:
        # fetch_jira_context es síncrono (Jira + Gemini) → fuera del event loop.
        context = await run_in_threadpool(
            fetch_jira_context,
            execution_id=execution_id,
            server=server,
            email=email,
            token=token,
            issue_key=issue_key,
            endpoints=endpoints_for_ai or None,
        )
    except Exception as e:
        logger.error("Error consultando Jira (fetch_jira_context): %s", e, exc_info=True)
        raise JiraContextFetchFailed() from e

    # Snapshot completo de la HU (best-effort): mantiene la HU en BD aun tras el
    # cleanup de 48h. Si falla, no bloquea la generación, pero deja traza.
    jira_issue_id = None
    try:
        service = await run_in_threadpool(
            JiraService, server=server, email=email, token=token
        )
        full_ticket = await run_in_threadpool(service.get_ticket_detail, issue_key)
        jira_issue = await upsert_jira_issue(
            db, user_id, full_ticket, structured_criteria=context
        )
        jira_issue_id = jira_issue.id
    except Exception as exc:
        logger.warning("No se pudo persistir el snapshot completo de la HU: %s", exc, exc_info=True)

    await execution_repo.set_jira_context(
        db,
        execution_id,
        issue_key=issue_key,
        summary=context.get("contexto_negocio", ""),
        jira_issue_id=jira_issue_id,
    )

    return FetchJiraResult(
        issue_key=issue_key,
        endpoints_with_criteria=len(context.get("endpoints", [])),
        business_summary=context.get("contexto_negocio", ""),
    )
