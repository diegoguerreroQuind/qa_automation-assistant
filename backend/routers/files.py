from datetime import datetime, timezone
import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.core.constants import CYPRESS_FEATURES_SUBDIR, CYPRESS_STEPS_SUBDIR
from backend.models.database import get_db
from backend.models.db import User, Project, Execution, GeneratedFile
from backend.schemas.executions import FileOut, FileUpdate
from backend.security.jwt import get_current_user
from backend.services.pipeline_service import get_cypress_project_dir
from backend.services.zip_builder import build_zip, build_zip_from_db

router = APIRouter(prefix="/executions", tags=["files"])


@router.get("/{execution_id}/files", response_model=list[FileOut])
async def list_files(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_ownership(execution_id, current_user.id, db)
    result = await db.execute(
        select(GeneratedFile).where(GeneratedFile.execution_id == execution_id)
    )
    return result.scalars().all()


@router.get("/{execution_id}/files/{filename}", response_model=FileOut)
async def get_file(
    execution_id: str,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_ownership(execution_id, current_user.id, db)
    result = await db.execute(
        select(GeneratedFile).where(
            GeneratedFile.execution_id == execution_id,
            GeneratedFile.file_name == filename,
        )
    )
    gf = result.scalar_one_or_none()
    if not gf:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return {"id": gf.id, "file_name": gf.file_name, "file_type": gf.file_type, "file_content": gf.file_content}


@router.patch("/{execution_id}/files/{filename}")
async def update_file(
    execution_id: str,
    filename: str,
    body: FileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """RF-004: Manual edits override AI-generated content in both DB and disk."""
    await _verify_ownership(execution_id, current_user.id, db)

    result = await db.execute(
        select(GeneratedFile).where(
            GeneratedFile.execution_id == execution_id,
            GeneratedFile.file_name == filename,
        )
    )
    gf = result.scalar_one_or_none()
    if not gf:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    await db.execute(
        update(GeneratedFile)
        .where(GeneratedFile.id == gf.id)
        .values(file_content=body.content, updated_at=datetime.now(timezone.utc))
    )
    await db.commit()

    # Mirror edit to disk so the next ZIP download reflects manual changes
    cypress_dir = get_cypress_project_dir(execution_id)
    disk_path = _resolve_disk_path(cypress_dir, filename)
    if disk_path.exists():
        disk_path.write_text(body.content, encoding="utf-8")

    return {"updated": filename}


@router.get("/{execution_id}/download")
async def download_zip(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Downloads the Cypress project as a ZIP.

    Primary path: reads files from the session directory on disk.
    Fallback path: if the directory was purged by the TTL cleanup, reconstructs
    the ZIP from the GeneratedFile rows stored in PostgreSQL (RF-005).
    """
    await _verify_ownership(execution_id, current_user.id, db)

    cypress_dir = get_cypress_project_dir(execution_id)

    if cypress_dir.exists():
        try:
            zip_bytes = build_zip(cypress_dir)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    else:
        # Filesystem was purged — rebuild ZIP from DB content
        result = await db.execute(
            select(GeneratedFile).where(GeneratedFile.execution_id == execution_id)
        )
        files = result.scalars().all()
        if not files:
            raise HTTPException(
                status_code=404,
                detail="No hay archivos generados para esta ejecución",
            )
        zip_bytes = build_zip_from_db(files)

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=cypress-project-{execution_id[:8]}.zip"
            )
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_disk_path(cypress_dir: Path, filename: str) -> Path:
    """
    Maps a generated filename to its absolute path on disk.

    Security: enforces a whitelist of allowed extensions and validates that
    the resolved path stays inside cypress_dir to prevent path traversal attacks.
    """
    # Whitelist: only .feature and .ts are valid generated file types
    if not (filename.endswith(".feature") or filename.endswith(".ts")):
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido")

    if filename.endswith(".feature"):
        candidate = cypress_dir / CYPRESS_FEATURES_SUBDIR / filename
    else:
        candidate = cypress_dir / CYPRESS_STEPS_SUBDIR / filename

    # Anti path-traversal: resolve symlinks and ".." segments, then verify containment
    resolved = candidate.resolve()
    if not str(resolved).startswith(str(cypress_dir.resolve())):
        raise HTTPException(status_code=403, detail="Acceso denegado")

    return resolved


async def _verify_ownership(execution_id: str, user_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(Execution)
        .join(Project, Execution.project_id == Project.id)
        .where(Execution.id == execution_id, Project.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
