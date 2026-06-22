import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.constants import CYPRESS_FEATURES_SUBDIR, CYPRESS_STEPS_SUBDIR
from backend.models.database import get_db
from backend.models.db import User
from backend.repositories import execution_repository as execution_repo
from backend.repositories import file_repository as file_repo
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
    return await file_repo.list_for_execution(db, execution_id)


@router.get("/{execution_id}/files/{filename}", response_model=FileOut)
async def get_file(
    execution_id: str,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_ownership(execution_id, current_user.id, db)
    gf = await file_repo.get_by_name(db, execution_id, filename)
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

    gf = await file_repo.get_by_name(db, execution_id, filename)
    if not gf:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    await file_repo.update_content(db, gf, body.content)

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
        files = await file_repo.list_for_execution(db, execution_id)
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

    Security: enforces a whitelist of allowed extensions, rechaza separadores de
    ruta en el nombre, y valida que la ruta resuelta quede DENTRO de cypress_dir
    (con is_relative_to, no con prefijos de string) para prevenir path traversal.
    """
    # Whitelist: only .feature and .ts are valid generated file types
    if not (filename.endswith(".feature") or filename.endswith(".ts")):
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido")

    # El nombre debe ser un archivo plano: sin separadores, sin "..", sin NUL.
    if filename != Path(filename).name or filename in {".", ".."} or "\x00" in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")

    if filename.endswith(".feature"):
        candidate = cypress_dir / CYPRESS_FEATURES_SUBDIR / filename
    else:
        candidate = cypress_dir / CYPRESS_STEPS_SUBDIR / filename

    # Anti path-traversal: resuelve symlinks/".." y verifica contención real.
    base = cypress_dir.resolve()
    resolved = candidate.resolve()
    if not resolved.is_relative_to(base):
        raise HTTPException(status_code=403, detail="Acceso denegado")

    return resolved


async def _verify_ownership(execution_id: str, user_id: str, db: AsyncSession) -> None:
    # Reutiliza la misma query de ownership del repositorio de ejecuciones.
    if not await execution_repo.get_execution_for_user(db, execution_id, user_id):
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
