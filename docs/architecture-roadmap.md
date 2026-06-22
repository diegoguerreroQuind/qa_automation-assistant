# Roadmap arquitectónico — QA AI Assistant (backend)

> Estado: **en progreso**. La capa de repositorios ya está introducida y aplicada
> al dominio de **ejecuciones** (`backend/repositories/execution_repository.py`)
> como plantilla. Este documento define el destino y los pasos restantes.

## Arquitectura objetivo: Modular Monolith

Organización por **módulos de negocio** (no por capas técnicas globales), sobre
infraestructura compartida. Se toman dos préstamos puntuales de Clean
Architecture **solo donde duele**: `repositories/` (aislar SQLAlchemy) y
`use_cases/`/servicios de aplicación (orquestación multi-paso). Nada de
puertos/adaptadores abstractos ni DDD táctico completo — sobreingeniería para un
equipo pequeño de innovación.

### Estructura objetivo

```
backend/  (futuro: src/qa_assistant/ con pyproject.toml, sin sys.path hacks)
├── main.py                 # FastAPI factory + CORS + middleware
├── config.py
├── shared/                 # infra transversal
│   ├── constants.py, state_machine.py   (hoy backend/core/)
│   ├── security/           # jwt, encryption, password, roles
│   ├── db/                 # engine, session, Base (hoy models/database.py)
│   └── redis_client.py
├── repositories/           # un repo por agregado (transición actual)
└── modules/
    ├── auth/         {router, service, repository, schemas, models}
    ├── projects/     {router, service, repository, schemas, models}
    ├── integrations/ {router, service, repository, schemas, models}
    ├── jira/         {router, service, schemas}
    └── generation/   # ← aquí aterriza TODO app/ + pipeline + tasks
        ├── router.py, use_cases/, repository.py, tasks.py
        ├── parsers/      (hoy app/parsers/)
        ├── generators/   (hoy app/generators/)
        └── ai/           (hoy app/ai/)
```

## Pasos restantes (incrementales, verificables uno a uno)

Prioridad por dolor (acceso DB inline + lógica de negocio en router):

1. **projects** (15 ops inline) → `project_repository` + mover serialización.
2. **files** (13 ops inline) → `file_repository` + endurecer anti-path-traversal
   (`is_relative_to` en vez de `startswith`).
3. **fetch_jira** → extraer la orquestación (~80 líneas) del router a un
   `execution_service.fetch_and_link_jira_context()` (use case).
4. **integrations / user_stories / auth** → repos respectivos.
5. **Fusionar `app/` en `backend/modules/generation/`**: elimina los
   `sys.path.insert` (`tasks/celery_app.py`, `generation_task.py`) y el riesgo
   del Dockerfile. Hacerlo cuando exista paquete instalable (`pyproject.toml`).
6. **OCP en providers** (oauth `_provider_config`, integrations `*_KEYS`):
   registro/strategy por provider en vez de if/elif paralelos.
7. **DIP en integraciones externas**: interfaces `LLMProvider` / `IssueTracker`
   inyectables (hoy `JiraService` instancia `JIRA(...)` y `generator` instancia
   `ChatGoogleGenerativeAI` directamente) — habilita mockear y el "multi-model
   support" que el código ya anuncia pero no implementa.

## Precondición: tests — ✅ HECHA (base)

Harness en `backend/tests/` (pytest + pytest-asyncio + httpx ASGITransport + DB
SQLite en memoria; `get_db` sobreescrito, revocación de token mockeada para no
depender de Redis). **24 tests** cubren happy path + 401/404 de auth, projects y
executions (esta última ejercita la capa de repositorios). Correr con:

```bash
./venv/bin/pip install -r requirements-dev.txt   # primera vez
./venv/bin/pytest
```

Ampliar la cobertura **a la par** que se refactoriza cada módulo (escribir los
tests del dominio antes/junto a moverlo a repositorio).

## Principio rector

Migrar **un dominio a la vez**, dejando el resto funcionando. Nada de big-bang.
