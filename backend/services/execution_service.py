"""
Service layer for Execution business logic.

Moves DB orchestration out of routers so handlers stay thin.
"""
import json

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from backend.core.state_machine import assert_valid_transition, InvalidStatusTransitionError
from backend.models.db import Endpoint, Execution, ExecutionStatus


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
