"""
AI generation core — Gemini-based BDD test and Jira context generation.

LLM clients are module-level singletons to avoid creating a new HTTP connection
on every endpoint generation call (which can be dozens per execution).
"""
import json
import os
import ssl
from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser

from app.ai.prompts.cypress_prompt import CYPRESS_CUCUMBER_PROMPT
from app.ai.prompts.jira_prompt import JIRA_PARSER_PROMPT

# ---------------------------------------------------------------------------
# Corporate network SSL workaround — only active when explicitly configured.
# Scoped to DISABLE_SSL_VERIFY=true to avoid silently disabling SSL globally.
# ---------------------------------------------------------------------------
if os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true":
    try:
        ssl._create_default_https_context = ssl._create_unverified_context
    except AttributeError:
        pass


_NO_KEY_MSG = (
    "No hay API key de Gemini configurada. Añádela en Credenciales (Modelo de IA) "
    "o define GOOGLE_API_KEY en el servidor."
)


def _resolve_google_api_key() -> str:
    """
    Resolves the Gemini key: GOOGLE_API_KEY env var first, then backend settings.

    pydantic-settings reads .env into the Settings object but does NOT populate
    os.environ, so we check both. Per-user credentials (stored in the DB) are
    resolved by the caller and passed explicitly as `api_key`.
    """
    key = os.getenv("GOOGLE_API_KEY", "")
    if not key:
        try:
            from backend.config import settings          # noqa: PLC0415
            key = getattr(settings, "google_api_key", "") or ""
        except Exception:
            pass
    return key


# ---------------------------------------------------------------------------
# LLM clients are built lazily and cached per API key (one HTTP client per key,
# reused across calls). Building at import time is avoided so a missing key never
# breaks the import — the error surfaces only when generation is actually invoked.
# ---------------------------------------------------------------------------
@lru_cache(maxsize=8)
def _cypress_llm(api_key: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model="gemini-pro-latest", temperature=0.1, google_api_key=api_key)


@lru_cache(maxsize=8)
def _jira_llm(api_key: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model="gemini-pro-latest", temperature=0.0, google_api_key=api_key)


def generar_test_cypress(
    endpoint_data: dict,
    casos_jira: list | None = None,
    api_key: str | None = None,
) -> dict:
    """
    Uses Gemini to generate BDD code for a single API endpoint.

    Args:
        endpoint_data: Dict with keys 'nombre_peticion', 'metodo', 'url', etc.
        casos_jira:    List of acceptance criteria from Jira (optional).
                       If None/empty, generates a single Happy Path scenario.

    Returns:
        {'feature': '<gherkin code>', 'steps': '<typescript code>'}

    Raises:
        ValueError: If the LLM response does not include the expected delimiters.
    """
    if casos_jira is None:
        casos_jira = []

    key = (api_key or _resolve_google_api_key()).strip()
    if not key:
        raise ValueError(_NO_KEY_MSG)

    chain = CYPRESS_CUCUMBER_PROMPT | _cypress_llm(key) | StrOutputParser()

    raw_response = chain.invoke({
        "endpoint_data": str(endpoint_data),
        "nombre_endpoint": endpoint_data.get("nombre_peticion", "endpoint_desconocido"),
        "casos_prueba_jira": (
            str(casos_jira) if casos_jira
            else "Generar solo un Happy Path exitoso."
        ),
    })

    # Strip markdown fences the LLM sometimes adds despite instructions
    raw_response = (
        raw_response
        .replace("```gherkin", "")
        .replace("```typescript", "")
        .replace("```ts", "")
        .replace("```", "")
        .strip()
    )

    try:
        parts = raw_response.split("===STEPS===")
        feature_part = parts[0].replace("===FEATURE===", "").strip()
        steps_part   = parts[1].strip()
        return {"feature": feature_part, "steps": steps_part}
    except IndexError:
        raise ValueError(
            "La IA no devolvió el formato esperado con los delimitadores "
            "===FEATURE=== / ===STEPS===."
        )


def estructurar_descripcion_jira(
    descripcion_cruda: str,
    api_json_context: str,
    api_key: str | None = None,
) -> dict:
    """
    Uses Gemini to cross-reference a raw Jira description with API endpoints,
    returning a structured dict with acceptance criteria per endpoint.

    Args:
        descripcion_cruda:  Raw text from the Jira issue description field.
        api_json_context:   JSON string of extracted endpoints (from api.json).

    Returns:
        Structured dict: { 'contexto_negocio': str, 'endpoints': [...] }

    Raises:
        ValueError: If the LLM response is not valid JSON.
    """
    key = (api_key or _resolve_google_api_key()).strip()
    if not key:
        raise ValueError(_NO_KEY_MSG)

    chain = JIRA_PARSER_PROMPT | _jira_llm(key) | StrOutputParser()

    raw_response = chain.invoke({
        "descripcion_jira": descripcion_cruda,
        "api_json_context": api_json_context,
    })

    clean_response = raw_response.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(clean_response)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Gemini no devolvió un JSON válido.\n"
            f"Respuesta recibida: {clean_response}\n"
            f"Error: {e}"
        )
