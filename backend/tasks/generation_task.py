"""
Celery task: generates BDD tests for each selected endpoint.

Architecture:
  generate_for_execution (orchestrator, ~40 lines)
    ├── _mark_execution_status()   — updates DB status
    ├── _fetch_endpoints()         — loads Endpoint rows from DB
    ├── _load_input_context()      — reads inputContext.json or fetches Jira
    ├── _generate_single_endpoint()— calls Gemini LLM
    ├── _write_to_disk()           — writes .feature and .ts files
    ├── _persist_endpoint_result() — upserts GeneratedFile rows in DB
    └── _publish_ws()              — Redis pub/sub → browser via FastAPI WS
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import logging

import redis as redis_sync
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

logger = logging.getLogger("qa_assistant.task")

from backend.config import settings
from backend.core.constants import CYPRESS_FEATURES_SUBDIR, CYPRESS_STEPS_SUBDIR
from backend.core.state_machine import assert_valid_transition, InvalidStatusTransitionError
from backend.models.db import (
    Endpoint, Execution, GeneratedFile,
    ExecutionStatus, EndpointStatus,
)
from backend.services.pipeline_service import get_session_dir, get_cypress_project_dir
from backend.tasks.celery_app import celery_app


# ---------------------------------------------------------------------------
# Internal data container for a generation result
# ---------------------------------------------------------------------------
class _GenerationResult(NamedTuple):
    endpoint: Endpoint
    safe_name: str
    feature_code: str
    steps_code: str


# ---------------------------------------------------------------------------
# Celery task — orchestrator (thin, delegates to private helpers)
# ---------------------------------------------------------------------------
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    time_limit=300,       # hard kill at 5 min — prevents zombie workers
    soft_time_limit=240,  # raises SoftTimeLimitExceeded at 4 min — allows clean shutdown
    name="backend.tasks.generation_task.generate_for_execution",
)
def generate_for_execution(
    self,
    execution_id: str,
    endpoint_ids: list[int],
    ai_model: str = "gemini-pro-latest",
    user_id: str | None = None,
):
    """
    Jira credentials are read from the encrypted credentials table — they are
    never serialized into Celery task arguments (which are stored in Redis in
    plain text).  The jira_issue_key is read from the Execution row in the DB.
    """
    engine = create_engine(_sync_db_url(), pool_pre_ping=True)
    session_dir = get_session_dir(execution_id)
    cypress_dir = get_cypress_project_dir(execution_id)

    # Read jira_issue_key from DB (not from task args) + validate state transition
    with Session(engine) as db:
        execution_row = db.get(Execution, execution_id)
        jira_issue_key = execution_row.jira_ticket_id if execution_row else None
        current_status = execution_row.status if execution_row else None

    jira_params = dict(
        user_id=user_id,
        issue_key=jira_issue_key,
        engine=engine,
    )

    try:
        # Guard: only valid states may transition into 'generating'
        try:
            assert_valid_transition(current_status, ExecutionStatus.generating)
        except InvalidStatusTransitionError as transition_err:
            _publish_ws(execution_id, {
                "type": "fatal_error",
                "message": str(transition_err),
            })
            # Raise directly — no retry makes sense for a logic error
            raise ValueError(str(transition_err)) from transition_err

        _mark_execution_status(engine, execution_id, ExecutionStatus.generating)
        endpoints = _fetch_endpoints(engine, execution_id, endpoint_ids)

        # Resolve the Gemini API key up front: env/settings → user credential.
        # Without it the LLM cannot run, so fail fast with an actionable message
        # instead of producing N identical per-endpoint auth errors (and no retry).
        gemini_key = _resolve_gemini_key(engine, user_id)
        if not gemini_key:
            msg = (
                "No hay API key de Gemini configurada. Añádela en Credenciales "
                "(Modelo de IA) o define GOOGLE_API_KEY en el servidor, y vuelve a generar."
            )
            for ep in endpoints:
                _mark_endpoint_status(engine, ep.id, EndpointStatus.error, error=msg)
            _mark_execution_status(engine, execution_id, ExecutionStatus.failed, endpoints_generated=0)
            _publish_ws(execution_id, {"type": "fatal_error", "message": msg})
            logger.error("Task aborted execution_id=%s: missing Gemini API key", execution_id)
            return

        input_context = _load_input_context(session_dir, execution_id, jira_params)
        api_data = _load_api_json(session_dir)  # headers + body for richer LLM prompts

        total = len(endpoints)
        logger.info("Task started execution_id=%s endpoints=%d api_endpoints=%d", execution_id, total, len(api_data))
        _publish_ws(execution_id, {"type": "started", "total": total})

        generated_count = 0
        for idx, ep in enumerate(endpoints, 1):
            try:
                result = _generate_single_endpoint(ep, input_context, api_data, gemini_key)
                _persist_endpoint_result(engine, execution_id, result)
                _write_to_disk(cypress_dir, result)
                _mark_endpoint_status(engine, ep.id, EndpointStatus.success)
                generated_count += 1
                _publish_ws(execution_id, {
                    "type": "file_ready",
                    "current": idx,
                    "total": total,
                    "endpoint": ep.name,
                    "files": [
                        f"{result.safe_name}.feature",
                        f"{result.safe_name}.ts",
                    ],
                })
            except Exception as ep_err:
                _mark_endpoint_status(
                    engine, ep.id, EndpointStatus.error, error=str(ep_err)
                )
                _publish_ws(execution_id, {
                    "type": "error",
                    "current": idx,
                    "total": total,
                    "endpoint": ep.name,
                    "message": str(ep_err),
                })

        # Precise final status: complete only if ALL endpoints succeeded
        if generated_count == total:
            final_status = ExecutionStatus.complete
        elif generated_count > 0:
            final_status = ExecutionStatus.partial
        else:
            final_status = ExecutionStatus.failed

        _mark_execution_status(
            engine, execution_id, final_status,
            endpoints_generated=generated_count,
        )
        logger.info(
            "Task finished execution_id=%s status=%s generated=%d/%d",
            execution_id, final_status, generated_count, total,
        )
        _publish_ws(execution_id, {
            "type": "complete",
            "status": final_status,
            "total": total,
            "generated": generated_count,
        })

    except InvalidStatusTransitionError:
        # Already published to WS and raised — do NOT mark failed or retry
        raise
    except SoftTimeLimitExceeded:
        # LLM call exceeded the 4-minute soft limit — clean shutdown before hard kill at 5 min
        _safe_mark_failed(engine, execution_id)
        _publish_ws(execution_id, {
            "type": "fatal_error",
            "message": "La generación superó el límite de tiempo (4 min). La ejecución fue cancelada.",
        })
        logger.error("Task timed out execution_id=%s", execution_id)
        raise  # do NOT retry — hitting the limit again is guaranteed
    except Exception as exc:
        _safe_mark_failed(engine, execution_id)
        _publish_ws(execution_id, {"type": "fatal_error", "message": str(exc)})
        logger.error("Task failed execution_id=%s error=%s", execution_id, exc, exc_info=True)
        raise self.retry(exc=exc)
    finally:
        # Libera el pool de conexiones en todas las rutas (éxito, fallo, retry):
        # un engine por tarea sin dispose fuga conexiones en el worker bajo carga.
        engine.dispose()


# ---------------------------------------------------------------------------
# Private helpers — each has exactly one responsibility
# ---------------------------------------------------------------------------

def _sync_db_url() -> str:
    return settings.sync_database_url


def _publish_ws(execution_id: str, event: dict) -> None:
    """Publish a progress event to Redis so FastAPI WS handler relays it to the browser."""
    client = redis_sync.from_url(settings.redis_url)
    try:
        client.publish(f"ws:{execution_id}", json.dumps(event))
    finally:
        client.close()


def _mark_execution_status(
    engine,
    execution_id: str,
    status: ExecutionStatus,
    endpoints_generated: int | None = None,
) -> None:
    values: dict = {"status": status}
    if endpoints_generated is not None:
        values["endpoints_generated"] = endpoints_generated
        values["completed_at"] = datetime.now(timezone.utc)
    with Session(engine) as db:
        db.execute(
            update(Execution).where(Execution.id == execution_id).values(**values)
        )
        db.commit()


def _safe_mark_failed(engine, execution_id: str) -> None:
    """Best-effort status update on fatal errors — never raises."""
    try:
        _mark_execution_status(engine, execution_id, ExecutionStatus.failed)
    except Exception:
        pass


def _mark_endpoint_status(
    engine,
    endpoint_id: int,
    status: EndpointStatus,
    error: str | None = None,
) -> None:
    values: dict = {"status": status}
    if error:
        values["error_message"] = error[:500]
    with Session(engine) as db:
        db.execute(update(Endpoint).where(Endpoint.id == endpoint_id).values(**values))
        db.commit()


def _fetch_endpoints(engine, execution_id: str, endpoint_ids: list[int]) -> list:
    """Loads the selected Endpoint rows from the DB as plain dicts to avoid session issues."""
    with Session(engine) as db:
        rows = db.execute(
            select(Endpoint).where(
                Endpoint.execution_id == execution_id,
                Endpoint.id.in_(endpoint_ids),
            )
        ).scalars().all()
        # Return detached copies as plain objects
        return [
            type("EP", (), {"id": r.id, "name": r.name, "method": r.method, "url": r.url})()
            for r in rows
        ]


def _load_input_context(
    session_dir: Path,
    execution_id: str,
    jira_params: dict,
) -> dict:
    """
    Returns structured Jira acceptance criteria.

    Priority:
    1. inputContext.json already on disk (most common path — set during fetch-jira step).
    2. Re-fetch from Jira on-the-fly using credentials from the encrypted DB table.
       Credentials are NEVER passed as task arguments; they are read here directly
       from the credentials table to keep tokens out of Redis/Celery serialization.
    3. Empty dict — generation still proceeds using only endpoint data (Happy Path).
    """
    context_path = session_dir / "inputContext.json"
    if context_path.exists():
        with open(context_path, encoding="utf-8") as f:
            return json.load(f)

    # Fallback: read Jira credentials from encrypted DB table.
    #
    # Best-effort: any failure here (credential decryption with a rotated
    # ENCRYPTION_KEY → InvalidTag, Jira network error, AI structuring error)
    # must NOT abort the whole generation. We degrade to Happy Path (empty
    # context) and publish a warning instead of letting the task crash.
    user_id = jira_params.get("user_id")
    issue   = jira_params.get("issue_key")
    engine  = jira_params.get("engine")

    if user_id and issue and engine:
        try:
            from backend.services.credentials_service import get_credential_sync
            server = get_credential_sync(engine, user_id, "jira", "server")
            email  = get_credential_sync(engine, user_id, "jira", "email")
            token  = get_credential_sync(engine, user_id, "jira", "token")

            if server and email and token:
                from backend.services.pipeline_service import fetch_jira_context
                return fetch_jira_context(
                    execution_id=execution_id,
                    server=server, email=email, token=token, issue_key=issue,
                )
        except Exception as jira_err:
            logger.warning("Jira context unavailable for %s: %s", execution_id, jira_err)
            _publish_ws(execution_id, {
                "type": "warning",
                "message": (
                    f"No se pudo cargar el contexto Jira: {jira_err}. "
                    "Se generará solo con Happy Path."
                ),
            })

    return {}


def _resolve_gemini_key(engine, user_id: str | None) -> str:
    """
    Resolves the Gemini API key for generation, in priority order:
      1. GOOGLE_API_KEY env var / backend settings (server-wide key).
      2. The user's encrypted `gemini`/`api_key` credential (self-service).

    Returns "" if no key is available. Credential decryption errors (e.g. a
    rotated ENCRYPTION_KEY → InvalidTag) are swallowed so they degrade to "no key"
    rather than crashing the task.
    """
    from backend.modules.generation.ai.generator import _resolve_google_api_key

    key = (_resolve_google_api_key() or "").strip()
    if key:
        return key

    if user_id:
        try:
            from backend.services.credentials_service import get_credential_sync
            return (get_credential_sync(engine, user_id, "gemini", "api_key") or "").strip()
        except Exception as exc:
            logger.warning("Could not read user Gemini credential: %s", exc)
    return ""


def _generate_single_endpoint(
    ep,
    input_context: dict,
    api_data: list,
    gemini_key: str,
) -> _GenerationResult:
    """
    Calls the Gemini LLM for one endpoint and returns a typed result.

    api_data is the full list loaded from api.json — used to enrich the
    endpoint payload with headers and body before sending to the LLM.

    NOTE: The `ai_model` field from the Execution record is stored in the DB and
    forwarded to this task, but the generator currently targets 'gemini-pro-latest'.
    Multi-model support is tracked for v1.1.
    """
    from backend.modules.generation.ai.generator import generar_test_cypress

    # Base payload (always present — stored in DB)
    endpoint_payload: dict = {
        "nombre_peticion": ep.name,
        "metodo": ep.method,
        "url": ep.url,
    }

    # Enrich with headers/body from api.json so the LLM can generate real cy.request calls
    for full_ep in api_data:
        if full_ep.get("nombre_peticion", "").lower() == ep.name.lower():
            if full_ep.get("headers"):
                endpoint_payload["headers"] = full_ep["headers"]
            if full_ep.get("body"):
                endpoint_payload["body"] = full_ep["body"]
            break

    casos_jira = _find_jira_cases(input_context, ep.name)
    result = generar_test_cypress(endpoint_payload, casos_jira or None, api_key=gemini_key)

    return _GenerationResult(
        endpoint=ep,
        safe_name=_safe_filename(ep.name),
        feature_code=result.get("feature", ""),
        steps_code=result.get("steps", ""),
    )


def _write_to_disk(cypress_dir: Path, result: _GenerationResult) -> None:
    """Writes .feature and .ts files to the Cypress project directory."""
    features_dir = cypress_dir / CYPRESS_FEATURES_SUBDIR
    steps_dir    = cypress_dir / CYPRESS_STEPS_SUBDIR
    features_dir.mkdir(parents=True, exist_ok=True)
    steps_dir.mkdir(parents=True, exist_ok=True)

    (features_dir / f"{result.safe_name}.feature").write_text(
        result.feature_code, encoding="utf-8"
    )
    (steps_dir / f"{result.safe_name}.ts").write_text(
        result.steps_code, encoding="utf-8"
    )


def _persist_endpoint_result(
    engine,
    execution_id: str,
    result: _GenerationResult,
) -> None:
    """Upserts GeneratedFile rows in the DB (supports re-generation idempotently)."""
    now = datetime.now(timezone.utc)
    files = [
        (f"{result.safe_name}.feature", "gherkin",    result.feature_code),
        (f"{result.safe_name}.ts",      "typescript", result.steps_code),
    ]
    with Session(engine) as db:
        for fname, ftype, content in files:
            existing = db.execute(
                select(GeneratedFile).where(
                    GeneratedFile.execution_id == execution_id,
                    GeneratedFile.file_name == fname,
                )
            ).scalar_one_or_none()

            if existing:
                existing.file_content = content
                existing.updated_at = now
            else:
                db.add(GeneratedFile(
                    execution_id=execution_id,
                    file_name=fname,
                    file_type=ftype,
                    file_content=content,
                ))
        db.commit()


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

import unicodedata


# Tokens irrelevantes para discriminar endpoints (ruido en HUs y nombres Postman).
_STOPWORDS = frozenset({
    "el", "la", "los", "las", "de", "del", "por", "para", "un", "una",
    "endpoint", "endpoints", "peticion", "peticiones", "servicio", "api",
    "enviar", "envia", "envio", "notificacion", "notificacion",
    "notificaciones", "request", "send", "the", "a",
})

# Sinónimos canal → familia de tokens equivalentes (cubre traducciones AI).
_SYNONYMS = {
    "email":      {"email", "correo", "electronico", "mail"},
    "push":       {"push"},
    "whatsapp":   {"whatsapp", "wpp", "wsp"},
    "sms":        {"sms"},
}


def _normalize(text: str) -> str:
    """Lowercase + strip accents, so 'electrónico' == 'electronico'."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _tokens(text: str) -> set[str]:
    """Significant tokens of a name (no stopwords, no punctuation)."""
    norm = _normalize(text)
    raw = [t.strip("_-./:,()[]") for t in norm.split()]
    return {t for t in raw if t and t not in _STOPWORDS}


def _expand_synonyms(tokens: set[str]) -> set[str]:
    """Expands tokens with their synonym family if any."""
    expanded = set(tokens)
    for key, family in _SYNONYMS.items():
        if expanded & family:
            expanded |= family
    return expanded


def _find_jira_cases(input_context: dict, endpoint_name: str) -> list | None:
    """
    Finds acceptance criteria for an endpoint with progressive matching:

      1. Substring bidirectional (fast, exact).
      2. Token-overlap with synonym expansion (handles AI translations,
         e.g. "endpoint de notificación por correo electrónico"
         ↔ "enviar notificacion Email" via the 'email'↔'correo' synonym).

    Returns the criterios_aceptacion list for the best match, or None.
    """
    ep_norm   = _normalize(endpoint_name)
    ep_tokens = _expand_synonyms(_tokens(endpoint_name))
    endpoints = input_context.get("endpoints", []) or []

    # Pass 1 — substring bidirectional
    for ep_ctx in endpoints:
        ctx_name = ep_ctx.get("nombre_endpoint", "")
        ctx_norm = _normalize(ctx_name)
        if ctx_norm and (ctx_norm in ep_norm or ep_norm in ctx_norm):
            return ep_ctx.get("criterios_aceptacion", [])

    # Pass 2 — token overlap with synonyms; choose the best (most overlap)
    best: tuple[int, list] | None = None
    for ep_ctx in endpoints:
        ctx_tokens = _expand_synonyms(_tokens(ep_ctx.get("nombre_endpoint", "")))
        overlap = len(ep_tokens & ctx_tokens)
        if overlap > 0 and (best is None or overlap > best[0]):
            best = (overlap, ep_ctx.get("criterios_aceptacion", []))

    return best[1] if best else None


def _load_api_json(session_dir: Path) -> list:
    """
    Loads the full endpoint list from api.json (saved during the extraction step).

    Returns the list of endpoint dicts (including headers and body) so the LLM
    can generate real cy.request() calls instead of empty placeholders.
    Falls back to an empty list if the file doesn't exist.
    """
    api_json_path = session_dir / "api.json"
    if api_json_path.exists():
        try:
            with open(api_json_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _safe_filename(name: str) -> str:
    """Converts an endpoint display name to a safe filesystem stem."""
    return (
        name.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .strip("_")
    )
