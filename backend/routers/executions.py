from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from backend.models.database import get_db
from backend.models.db import User, Project, Execution, Endpoint, ExecutionStatus
from backend.schemas.executions import (
    ExecutionCreate,
    EndpointOut,
    EndpointSelectionUpdate,
    GenerateRequest,
    GenerationJobResponse,
    FetchJiraRequest,
    FetchJiraResponse,
)
from backend.schemas.projects import ExecutionSummary
from backend.security.jwt import get_current_user
from backend.services.credentials_service import get_credential
from backend.services.execution_service import save_extracted_endpoints
from backend.services.jira_persistence import upsert_jira_issue
from backend.services.jira_service import JiraService
from backend.services.pipeline_service import get_session_dir, extract_and_scaffold

router = APIRouter(prefix="/executions", tags=["executions"])

_MAX_COLLECTION_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# 1. CREATE EXECUTION
# ---------------------------------------------------------------------------
@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_execution(
    body: ExecutionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Creates an execution record tied to a project."""
    await _require_project_ownership(body.project_id, current_user.id, db)

    execution = Execution(
        project_id=body.project_id,
        jira_ticket_id=body.jira_ticket_id,
        ai_model=body.ai_model,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Create isolated session directory (UUID-based → RNF-002)
    session_dir = get_session_dir(execution.id)
    (session_dir / "uploads").mkdir(parents=True, exist_ok=True)

    return {"execution_id": execution.id, "status": execution.status}


# ---------------------------------------------------------------------------
# 2. UPLOAD FILES
# ---------------------------------------------------------------------------
@router.post("/{execution_id}/upload")
async def upload_files(
    execution_id: str,
    collection: UploadFile = File(..., description="Postman Collection JSON"),
    environment: UploadFile | None = File(None, description="Postman Environment JSON"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Receives Postman collection and optional environment file (multipart/form-data)."""
    await _require_execution_ownership(execution_id, current_user.id, db)

    uploads_dir = get_session_dir(execution_id) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    if not (collection.filename or "").endswith(".json"):
        raise HTTPException(status_code=422, detail="La colección debe ser un archivo .json")

    # Fast-path: reject before reading if Content-Length header is available
    if collection.size is not None and collection.size > _MAX_COLLECTION_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"La colección supera el límite de {_MAX_COLLECTION_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    collection_bytes = await collection.read()

    # Definitive check after reading (guards against missing Content-Length)
    if len(collection_bytes) > _MAX_COLLECTION_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"La colección supera el límite de {_MAX_COLLECTION_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    collection_path = uploads_dir / "collection.json"
    collection_path.write_bytes(collection_bytes)

    if environment:
        (uploads_dir / "environment.json").write_bytes(await environment.read())

    return {"status": "uploaded", "collection": collection.filename}


# ---------------------------------------------------------------------------
# 3. EXTRACT ENDPOINTS (parses Postman → creates Cypress scaffold)
# ---------------------------------------------------------------------------
@router.post("/{execution_id}/extract", response_model=list[EndpointOut])
async def extract_endpoints(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Runs app/parsers/postman.py + app/generators/cypress.py.
    Returns the list of detected endpoints for the user to review (RF-002).
    """
    await _require_execution_ownership(execution_id, current_user.id, db)

    uploads_dir = get_session_dir(execution_id) / "uploads"
    collection_path = uploads_dir / "collection.json"
    env_path = uploads_dir / "environment.json"

    if not collection_path.exists():
        raise HTTPException(status_code=400, detail="Primero sube la colección de Postman")

    try:
        endpoints_data = extract_and_scaffold(
            execution_id=execution_id,
            collection_path=collection_path,
            environment_path=env_path if env_path.exists() else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Formato de colección inválido: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando colección: {e}")

    if not endpoints_data:
        raise HTTPException(status_code=422, detail="No se detectaron endpoints en la colección")

    # Delegate persistence and status update to the service layer
    return await save_extracted_endpoints(db, execution_id, endpoints_data)


# ---------------------------------------------------------------------------
# 4. FETCH JIRA CONTEXT (structures criteria via AI)
# ---------------------------------------------------------------------------
@router.post("/{execution_id}/fetch-jira", response_model=FetchJiraResponse)
async def fetch_jira(
    execution_id: str,
    body: FetchJiraRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetches a Jira ticket, uses AI to structure its acceptance criteria
    against the extracted endpoints, and saves inputContext.json.
    RF-003: credentials are passed per-request (never stored in plaintext).
    """
    execution = await _require_execution_ownership(execution_id, current_user.id, db)

    server = await get_credential(db, current_user.id, "jira", "server")
    email  = await get_credential(db, current_user.id, "jira", "email")
    token  = await get_credential(db, current_user.id, "jira", "token")

    if not server or not email or not token:
        raise HTTPException(
            status_code=424,
            detail=(
                "Credenciales Jira no configuradas. "
                "Guárdalas primero en PUT /credentials."
            ),
        )

    from backend.services.pipeline_service import fetch_jira_context

    # Load endpoint names from the DB (durable source of truth) so the AI anchors
    # acceptance criteria to the EXACT Postman names — even if /tmp/api.json was purged.
    ep_rows = (
        await db.execute(
            select(Endpoint).where(Endpoint.execution_id == execution_id)
        )
    ).scalars().all()

    # Hard guard: without endpoints in the DB, the AI invents endpoint names from
    # the HU text and the criteria won't match anything during generation.
    # Enforce the correct flow: upload → extract → fetch-jira.
    if not ep_rows:
        raise HTTPException(
            status_code=409,
            detail=(
                "No hay endpoints registrados para esta ejecución. "
                "Sube la colección Postman y ejecuta POST /executions/{id}/extract "
                "antes de vincular el ticket Jira."
            ),
        )

    endpoints_for_ai = [
        {"nombre_peticion": ep.name, "metodo": ep.method, "url": ep.url}
        for ep in ep_rows
    ]

    try:
        context = fetch_jira_context(
            execution_id=execution_id,
            server=server,
            email=email,
            token=token,
            issue_key=body.issue_key,
            endpoints=endpoints_for_ai or None,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error consultando Jira: {e}")

    # Fetch the FULL Jira issue (description + metadata) and persist it,
    # storing the AI-structured criteria alongside. This keeps the complete HU
    # in the DB even after the 48h session cleanup wipes inputContext.json.
    jira_issue_id = None
    try:
        service = JiraService(server=server, email=email, token=token)
        full_ticket = service.get_ticket_detail(body.issue_key)
        jira_issue = await upsert_jira_issue(
            db, current_user.id, full_ticket, structured_criteria=context
        )
        jira_issue_id = jira_issue.id
    except Exception:
        # Persisting the full snapshot is best-effort — never block generation
        jira_issue_id = None

    # Update execution with ticket info + link to the full HU record
    await db.execute(
        update(Execution)
        .where(Execution.id == execution_id)
        .values(
            jira_ticket_id=body.issue_key,
            jira_ticket_summary=context.get("contexto_negocio", ""),
            jira_issue_id=jira_issue_id,
        )
    )
    await db.commit()

    endpoint_count = len(context.get("endpoints", []))
    return FetchJiraResponse(
        issue_key=body.issue_key,
        context_ready=True,
        endpoints_with_criteria=endpoint_count,
        business_summary=context.get("contexto_negocio", ""),
    )


# ---------------------------------------------------------------------------
# 5. UPDATE ENDPOINT SELECTION (RF-002)
# ---------------------------------------------------------------------------
@router.patch("/{execution_id}/endpoints")
async def update_endpoint_selection(
    execution_id: str,
    body: EndpointSelectionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle which endpoints will be sent to AI generation."""
    await _require_execution_ownership(execution_id, current_user.id, db)

    # Deselect all, then select chosen ones
    await db.execute(
        update(Endpoint)
        .where(Endpoint.execution_id == execution_id)
        .values(selected=False)
    )
    if body.selected_ids:
        await db.execute(
            update(Endpoint)
            .where(
                Endpoint.execution_id == execution_id,
                Endpoint.id.in_(body.selected_ids),
            )
            .values(selected=True)
        )

    await db.execute(
        update(Execution)
        .where(Execution.id == execution_id)
        .values(endpoints_selected=len(body.selected_ids))
    )
    await db.commit()
    return {"updated": len(body.selected_ids)}


# ---------------------------------------------------------------------------
# 6. TRIGGER GENERATION (Celery)
# ---------------------------------------------------------------------------
@router.post("/{execution_id}/generate", response_model=GenerationJobResponse)
async def generate_tests(
    execution_id: str,
    body: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enqueues a Celery task to generate BDD tests for all selected endpoints."""
    execution = await _require_execution_ownership(execution_id, current_user.id, db)

    result = await db.execute(
        select(Endpoint).where(
            Endpoint.execution_id == execution_id,
            Endpoint.selected.is_(True),
        )
    )
    selected = result.scalars().all()

    if not selected:
        raise HTTPException(
            status_code=400,
            detail="No hay endpoints seleccionados. Usa PATCH /endpoints primero.",
        )

    from backend.tasks.generation_task import generate_for_execution

    # Jira credentials are NOT passed here — the worker reads them directly
    # from the encrypted credentials table to keep tokens out of Redis/Celery args.
    task = generate_for_execution.delay(
        execution_id=execution_id,
        endpoint_ids=[ep.id for ep in selected],
        ai_model=execution.ai_model,
        user_id=current_user.id,
    )

    return GenerationJobResponse(
        job_id=task.id,
        status="queued",
        execution_id=execution_id,
    )


# ---------------------------------------------------------------------------
# 7. GET EXECUTION BY ID
# ---------------------------------------------------------------------------
@router.get("/{execution_id}", response_model=ExecutionSummary)
async def get_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the current status and summary of a single execution.

    Use this to poll progress when the WebSocket connection is unavailable
    (e.g., after a page reload during generation).
    """
    execution = await _require_execution_ownership(execution_id, current_user.id, db)
    return execution


# ---------------------------------------------------------------------------
# 8. LIST ENDPOINTS
# ---------------------------------------------------------------------------
@router.get("/{execution_id}/endpoints", response_model=list[EndpointOut])
async def list_endpoints(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_execution_ownership(execution_id, current_user.id, db)
    result = await db.execute(
        select(Endpoint).where(Endpoint.execution_id == execution_id)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
async def _require_project_ownership(
    project_id: str, user_id: str, db: AsyncSession
) -> None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")


async def _require_execution_ownership(
    execution_id: str, user_id: str, db: AsyncSession
) -> Execution:
    result = await db.execute(
        select(Execution)
        .join(Project, Execution.project_id == Project.id)
        .where(Execution.id == execution_id, Project.user_id == user_id)
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return execution
