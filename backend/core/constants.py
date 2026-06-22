"""
Shared constants for the QA AI Assistant backend.

Centralizes paths and magic values used across multiple modules
to avoid duplication and make changes easy to propagate.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Cypress project directory layout
# These subdirectory paths are relative to the cypress-project root.
# Used by: generation_task.py, routers/files.py, services/zip_builder.py
# ---------------------------------------------------------------------------
CYPRESS_FEATURES_SUBDIR = Path("cypress") / "e2e" / "features"
CYPRESS_STEPS_SUBDIR    = Path("cypress") / "e2e" / "step_definitions"
CYPRESS_SUPPORT_SUBDIR  = Path("cypress") / "support"
