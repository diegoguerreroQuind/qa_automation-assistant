import io
import zipfile
from pathlib import Path

from backend.core.constants import CYPRESS_FEATURES_SUBDIR, CYPRESS_STEPS_SUBDIR


def build_zip(project_dir: Path) -> bytes:
    """
    Compresses the Cypress project directory into a ZIP and returns bytes.

    Raises ValueError if the resulting ZIP contains no .feature files — which
    would indicate a generation failure or an empty project directory.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in project_dir.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(project_dir.parent))

    result = buf.getvalue()
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        if not any(name.endswith(".feature") for name in zf.namelist()):
            raise ValueError(
                "El proyecto Cypress no contiene archivos .feature. "
                "Asegúrate de que la generación completó correctamente."
            )
    return result


def build_zip_from_db(files: list, project_name: str = "cypress-project") -> bytes:
    """
    Builds a ZIP from GeneratedFile ORM rows when the physical directory
    has been purged by the session TTL cleanup.

    Files are placed in the standard Cypress layout:
      - .feature  → <project_name>/cypress/e2e/features/
      - .ts       → <project_name>/cypress/e2e/step_definitions/
      - other     → <project_name>/
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for gf in files:
            if gf.file_name.endswith(".feature"):
                arc_path = Path(project_name) / CYPRESS_FEATURES_SUBDIR / gf.file_name
            elif gf.file_name.endswith(".ts"):
                arc_path = Path(project_name) / CYPRESS_STEPS_SUBDIR / gf.file_name
            else:
                arc_path = Path(project_name) / gf.file_name
            zf.writestr(str(arc_path), gf.file_content)

    return buf.getvalue()
