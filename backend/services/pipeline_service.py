import json
import re
import shutil
from pathlib import Path
from backend.config import settings

# Placeholder de Postman: {{nombre-variable}}
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([^}\s]+)\s*\}\}")


def _collect_placeholders(*texts: str | None) -> list[str]:
    """Extrae los nombres de variables {{x}} presentes en los textos dados (sin duplicar)."""
    found: list[str] = []
    for text in texts:
        if not text:
            continue
        for name in _PLACEHOLDER_RE.findall(text):
            if name not in found:
                found.append(name)
    return found


def _resolve_endpoint(endpoint: dict, env_vars: dict[str, str]) -> dict:
    """
    Enriquece un endpoint con:
      - `variables`: {placeholder: valor_resuelto} para las variables usadas
        (url + headers + body). El valor se toma del Environment ("" si no existe).
      - `url_resuelta`: la URL con cada {{x}} sustituido por su valor del Environment
        (deja el placeholder intacto si la variable no está en el Environment).
    """
    url = endpoint.get("url", "") or ""
    headers = endpoint.get("headers") or {}
    body = endpoint.get("body")

    header_text = " ".join(str(v) for v in headers.values()) if isinstance(headers, dict) else ""
    used = _collect_placeholders(url, header_text, body)

    variables = {name: env_vars.get(name, "") for name in used}

    resolved_url = url
    for name in used:
        value = env_vars.get(name)
        if value:
            resolved_url = resolved_url.replace(f"{{{{{name}}}}}", value)

    endpoint["variables"] = variables
    endpoint["url_resuelta"] = resolved_url
    return endpoint


def get_session_dir(execution_id: str) -> Path:
    return Path(settings.sessions_base_dir) / execution_id


def get_cypress_project_dir(execution_id: str) -> Path:
    return get_session_dir(execution_id) / "cypress-project"


def extract_and_scaffold(
    execution_id: str,
    collection_path: Path,
    environment_path: Path | None,
) -> list[dict]:
    """
    Runs Postman extraction and Cypress scaffolding.
    Returns list of cleaned endpoints.
    """
    from backend.modules.generation.parsers.postman import extraer_peticiones
    from backend.modules.generation.parsers.environment import extraer_variables_entorno
    from backend.modules.generation.generators.cypress import crear_estructura_cypress

    session_dir = get_session_dir(execution_id)
    cypress_dir = get_cypress_project_dir(execution_id)

    # Load Postman collection
    with open(collection_path, encoding="utf-8") as f:
        collection_data = json.load(f)

    items = collection_data.get("item", [])
    endpoints = extraer_peticiones(items)

    # Load environment variables if provided
    env_vars = {}
    if environment_path and environment_path.exists():
        env_vars = extraer_variables_entorno(str(environment_path))

    # Resolve {{placeholders}} against the environment so the UI can show both the
    # original Postman URL and the resolved one (+ which variables were used).
    for endpoint in endpoints:
        _resolve_endpoint(endpoint, env_vars)

    # Save cleaned API JSON to session dir
    api_json_path = session_dir / "api.json"
    with open(api_json_path, "w", encoding="utf-8") as f:
        json.dump(endpoints, f, ensure_ascii=False, indent=2)

    # Save env vars JSON for traceability / re-use
    if env_vars:
        env_json_path = session_dir / "environment.json"
        with open(env_json_path, "w", encoding="utf-8") as f:
            json.dump(env_vars, f, ensure_ascii=False, indent=2)

    # Scaffold Cypress project — pass env_vars so cypress.env.json is populated
    crear_estructura_cypress(cypress_dir, env_vars=env_vars if env_vars else {})

    return endpoints


def fetch_jira_context(
    execution_id: str,
    server: str,
    email: str,
    token: str,
    issue_key: str,
    endpoints: list[dict] | None = None,
) -> dict:
    """
    Fetches Jira ticket and uses AI to structure acceptance criteria.
    Returns the inputContext dict.

    Endpoint context priority (so the AI anchors criteria to the EXACT endpoint
    names and the generation step can match them):
      1. `endpoints` arg — pass the DB endpoint rows (durable source of truth).
      2. api.json on disk — written during extraction.
      3. Empty list — extract not run; AI structures without endpoint anchors.

    Passing the DB endpoints is critical: /tmp/api.json can be purged by the
    48h TTL cleanup, and without endpoint names the AI invents descriptive ones
    that won't match the real Postman names during generation.
    """
    from backend.modules.generation.parsers.jira_extractor import extraer_historia_jira
    from backend.modules.generation.ai.generator import estructurar_descripcion_jira

    session_dir = get_session_dir(execution_id)
    api_json_path = session_dir / "api.json"

    # Ensure session directory exists
    session_dir.mkdir(parents=True, exist_ok=True)

    jira_data = extraer_historia_jira(server, email, token, issue_key)

    # Resolve endpoint context with the priority described above
    if endpoints:
        api_context = endpoints
    elif api_json_path.exists():
        with open(api_json_path, encoding="utf-8") as f:
            api_context = json.load(f)
    else:
        # Extract not run yet — proceed without endpoint context
        api_context = []

    raw_description = jira_data.get("descripcion", "").strip()
    if not raw_description:
        raise ValueError(
            f"El ticket {issue_key} no tiene descripción. "
            "Agrega criterios de aceptación en Jira antes de continuar."
        )

    input_context = estructurar_descripcion_jira(raw_description, json.dumps(api_context))

    # Persist inputContext.json in session
    context_path = session_dir / "inputContext.json"
    with open(context_path, "w", encoding="utf-8") as f:
        json.dump(input_context, f, ensure_ascii=False, indent=2)

    return input_context
