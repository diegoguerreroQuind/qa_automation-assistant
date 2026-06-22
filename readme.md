# QA AI Assistant — Backend

Plataforma web impulsada por IA que **convierte colecciones Postman + Historias
de Usuario de Jira en proyectos Cypress BDD (Cucumber)** listos para ejecutar.
Democratiza la automatización de pruebas de API para QAs no técnicos.

Este repositorio contiene el **backend** (API + motor de generación). El
**frontend** (React + Vite) vive en un repositorio independiente:
**`qa-assistant-frontend`**. El contrato entre ambos es una API HTTP + JWT
(variables `VITE_API_URL` / `VITE_WS_URL` en el frontend; `ALLOWED_ORIGINS` aquí).

---

## Tabla de contenidos

- [¿Qué hace?](#qué-hace)
- [Stack tecnológico](#stack-tecnológico)
- [Arquitectura](#arquitectura)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Requisitos previos](#requisitos-previos)
- [Puesta en marcha (local)](#puesta-en-marcha-local)
- [Ejecución](#ejecución)
- [Tests](#tests)
- [Variables de entorno](#variables-de-entorno)
- [Flujo de uso (pipeline)](#flujo-de-uso-pipeline)
- [Referencia de la API](#referencia-de-la-api)
- [Gotchas y troubleshooting](#gotchas-y-troubleshooting)

---

## ¿Qué hace?

A partir de una colección Postman (y, opcionalmente, una HU de Jira), el sistema:

1. **Extrae** los endpoints de la colección Postman y arma un esqueleto Cypress.
2. **Estructura** los criterios de aceptación de la HU de Jira con IA (Gemini),
   anclándolos a los endpoints reales.
3. **Genera** archivos `.feature` (Gherkin) y `.ts` (step definitions) por
   endpoint, mediante una tarea asíncrona (Celery), reportando progreso en vivo
   por WebSocket.
4. **Entrega** el proyecto Cypress completo como ZIP descargable.

Las credenciales de Jira/Gemini se guardan **cifradas (AES-256-GCM)** por
usuario/proyecto y nunca viajan en texto plano ni en los argumentos de Celery.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| API | **FastAPI** 0.115 + Uvicorn (ASGI, async) |
| Tareas asíncronas | **Celery** 5.4 + **Redis** (broker + result backend + pub/sub de WebSocket) |
| Base de datos | **PostgreSQL** (async `asyncpg` para la API; sync `psycopg2` para Celery/Alembic) |
| ORM / migraciones | **SQLAlchemy** 2.0 + **Alembic** |
| Auth | **JWT** (`python-jose`) + **OAuth2** SSO (Google / Jira) + bcrypt |
| Cifrado de credenciales | **AES-256-GCM** (`cryptography`) |
| IA | **Gemini** vía `langchain-google-genai` |
| Integraciones | `jira` (REST API de Jira) |
| Config | `pydantic-settings` |
| Tests | `pytest` + `pytest-asyncio` + `httpx` |

**Python 3.11.9** (ver `.python-version`).

---

## Arquitectura

**Monolito modular** organizado por capas técnicas, con préstamos puntuales de
Clean Architecture donde aporta valor:

```
HTTP (routers)  →  servicios / use cases  →  repositories  →  SQLAlchemy
                         ↘ tasks Celery (generación asíncrona)
```

- **routers/** — orquestación HTTP delgada (auth, validación, traducción a
  respuestas/errores). No construyen SQL.
- **repositories/** — todo el acceso a datos (`execution`, `project`, `file`).
  Aísla SQLAlchemy → testeable y mockeable.
- **services/** — lógica de negocio y *use cases* (p.ej.
  `execution_service.fetch_and_link_jira_context`, que orquesta credenciales →
  Jira → IA → persistencia y señala errores de dominio).
- **modules/generation/** — el motor de generación (parsers de Postman/Jira,
  generador Cypress y prompts de IA).
- **tasks/** — la tarea Celery que genera los tests endpoint por endpoint.

> El plan de evolución arquitectónica y los pasos pendientes están en
> [`docs/architecture-roadmap.md`](docs/architecture-roadmap.md).

---

## Estructura del proyecto

```
.
├── backend/
│   ├── main.py              # App FastAPI: CORS, middleware de logging, lifespan
│   ├── config.py            # Settings (pydantic-settings) leídas de .env
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── core/                # Infra transversal: constants, state_machine
│   ├── models/              # database.py (engine/sesión), db.py (modelos SQLAlchemy)
│   ├── schemas/             # DTOs Pydantic por dominio
│   ├── routers/             # Endpoints HTTP
│   ├── repositories/        # Acceso a datos (execution / project / file)
│   ├── services/            # Lógica de negocio / use cases
│   ├── security/            # jwt, encryption, password, roles
│   ├── tasks/               # celery_app, generation_task
│   ├── modules/
│   │   └── generation/      # Motor de generación
│   │       ├── ai/          # generator + prompts (Gemini)
│   │       ├── parsers/     # postman, jira_extractor, environment
│   │       └── generators/  # scaffolding Cypress
│   └── tests/               # Suite pytest
├── alembic/                 # Migraciones de BD
├── scripts/                 # dev.sh (arranca todo), stop.sh
├── docs/                    # Roadmap arquitectónico, setup GCP
├── postman/                 # Colección Postman de referencia
├── docker-compose.yml       # Redis + backend + worker (la BD es externa)
├── alembic.ini
├── pytest.ini
├── requirements-dev.txt     # Dependencias solo de test
└── .env.example             # Plantilla de variables (copiar a .env)
```

---

## Requisitos previos

| Herramienta | Versión | Notas |
|---|---|---|
| Python | 3.11.x | `pyenv` recomendado (ver `.python-version`) |
| PostgreSQL | 14+ | Local (Postgres.app en macOS) o GCP Cloud SQL. Debe existir la BD `qa_assistant` |
| Redis | 6+ | `brew install redis` (macOS) o Docker |
| Gemini API key | — | Solo para *generar* tests. [Google AI Studio](https://aistudio.google.com/apikey) |

> Alternativa con Docker: ver [Ejecución → Docker Compose](#opción-c--docker-compose).

---

## Puesta en marcha (local)

### 1. Clonar y crear el entorno virtual

```bash
git clone <URL_DEL_REPO> qa-api-automation-assistant
cd qa-api-automation-assistant

python3.11 -m venv venv
source venv/bin/activate                 # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
pip install -r requirements-dev.txt      # opcional, para correr los tests
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` y, como mínimo, completa:

```bash
# Genera los secretos:
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
python3 -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_bytes(32).hex())"
```

Pega esos valores en `SECRET_KEY` y `ENCRYPTION_KEY`, y ajusta `DATABASE_URL`
con tu usuario/clave de Postgres. (Detalle completo en
[Variables de entorno](#variables-de-entorno).)

### 3. Crear la base de datos

```bash
# Con Postgres local (ajusta el usuario a tu instalación)
createdb qa_assistant
```

### 4. Aplicar migraciones

```bash
PYTHONPATH=. ./venv/bin/alembic upgrade head
```

> `init_db()` crea tablas faltantes al arrancar **solo fuera de producción**; el
> esquema canónico lo gestiona **Alembic**. En producción usa siempre Alembic.

---

## Ejecución

### Opción A — todo con un comando (recomendado, macOS)

```bash
./scripts/dev.sh
```

Verifica/levanta PostgreSQL y Redis, aplica migraciones, arranca **Uvicorn**
(`:8000`, con `--reload`) y el **worker Celery**, y muestra logs combinados.
`Ctrl+C` detiene FastAPI + Celery (Postgres y Redis siguen vivos). Para
detenerlo también: `./scripts/stop.sh`.

### Opción B — manual (dos terminales)

```bash
# Terminal 1 — API
PYTHONPATH=. ./venv/bin/uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Worker Celery (¡imprescindible para generar tests!)
PYTHONPATH=. ./venv/bin/celery -A backend.tasks.celery_app worker --loglevel=info --concurrency=4
```

### Opción C — Docker Compose

Levanta Redis + backend + worker (la **BD Postgres es externa**, configúrala en `.env`):

```bash
cp .env.example .env   # completar DATABASE_URL apuntando a tu Postgres
docker-compose up -d
```

### Verificar que está arriba

```bash
curl http://localhost:8000/health      # {"status":"ok",...}
```

- **API:** http://localhost:8000
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## Tests

```bash
pip install -r requirements-dev.txt   # primera vez
./venv/bin/pytest                     # 45 tests
```

Los tests usan **SQLite en memoria** y mockean Redis, así que **no requieren
Postgres ni Redis corriendo**. Cubren auth, projects, executions y files
(incluyendo casos de path-traversal).

---

## Variables de entorno

Todas se definen en `.env` (plantilla en `.env.example`).

| Variable | Requerida | Descripción |
|---|:---:|---|
| `DATABASE_URL` | ✅ | URL async de Postgres: `postgresql+asyncpg://USER:PASS@HOST:5432/qa_assistant` |
| `SECRET_KEY` | ✅ | Clave de firma JWT. Generar con `secrets.token_hex(32)` |
| `ENCRYPTION_KEY` | ✅* | AES-256 (64 hex) para cifrar credenciales. **Obligatoria en producción**; sin ella, cifrar/descifrar falla en runtime. Si se pierde, las credenciales cifradas son irrecuperables |
| `REDIS_URL` | ✅ | Redis para WebSocket pub/sub y revocación de JWT |
| `CELERY_BROKER_URL` | ✅ | Broker de Celery (Redis) |
| `CELERY_RESULT_BACKEND` | ✅ | Backend de resultados de Celery (Redis) |
| `GOOGLE_API_KEY` | ⚠️ | API key de Gemini. Necesaria para **generar** tests (o configúrala por usuario en Credenciales) |
| `JWT_ALGORITHM` | — | Por defecto `HS256` |
| `JWT_EXPIRE_HOURS` | — | Vigencia del token (por defecto `12`) |
| `ALLOWED_ORIGINS` | — | Orígenes CORS (JSON array). En prod, añade el dominio del frontend |
| `FRONTEND_URL` | — | Destino del redirect tras el callback OAuth |
| `SESSIONS_BASE_DIR` | — | Directorio temporal de sesiones (por defecto `/tmp/qa-sessions`) |
| `SESSION_TTL_HOURS` | — | TTL de limpieza de sesiones en disco (por defecto `48`) |
| `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI` | — | SSO Google (opcional; sin esto, el login Google redirige con error) |
| `JIRA_CLIENT_ID/SECRET/REDIRECT_URI` | — | SSO Jira/Atlassian (opcional) |
| `DISABLE_SSL_VERIFY` | — | `true` solo si un proxy SSL corporativo rompe la verificación de certificados |
| `ENVIRONMENT` | — | `development` (por defecto) o `production` |

\* `ENCRYPTION_KEY` puede ir vacía en dev hasta que uses credenciales cifradas;
es obligatoria si `ENVIRONMENT=production`.

> El login **email/contraseña funciona sin configurar nada de OAuth**. El SSO
> (Google/Jira) es opcional y requiere registrar las apps OAuth.

---

## Flujo de uso (pipeline)

El orden de la API para generar un proyecto Cypress:

1. `POST /auth/register` → `POST /auth/login` → obtienes el **JWT** (header
   `Authorization: Bearer <token>` en todo lo demás).
2. `POST /projects` → crea un proyecto.
3. `POST /executions` → crea una ejecución dentro del proyecto.
4. `POST /executions/{id}/upload` → sube la colección Postman (`.json`, máx 10 MB)
   y, opcionalmente, el environment.
5. `POST /executions/{id}/extract` → extrae endpoints y arma el esqueleto Cypress.
6. *(Opcional)* `POST /executions/{id}/fetch-jira` → estructura los criterios de
   la HU con IA (requiere credenciales Jira guardadas).
7. `PATCH /executions/{id}/endpoints` → selecciona qué endpoints generar.
8. `POST /executions/{id}/generate` → encola la generación en Celery.
9. **WebSocket** `ws://localhost:8000/ws/executions/{id}?token=<JWT>` → progreso
   en vivo (fallback: *polling* a `GET /executions/{id}` mientras `status=generating`).
10. `GET /executions/{id}/download` → descarga el proyecto Cypress como ZIP.

---

## Referencia de la API

La referencia interactiva y siempre actualizada está en **`/docs`**. Resumen por área:

| Área | Endpoints |
|---|---|
| **Auth** | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/logout` |
| **SSO** | `GET /auth/{provider}/login`, `GET /auth/{provider}/callback` (`provider` = `google`\|`jira`) |
| **Proyectos** | `GET/POST /projects`, `GET/PUT/DELETE /projects/{id}`, `GET /projects/{id}/executions` |
| **Ejecuciones** | `POST /executions`, `GET /executions/{id}`, `POST .../upload`, `POST .../extract`, `POST .../fetch-jira`, `PATCH .../endpoints`, `GET .../endpoints`, `POST .../generate` |
| **Archivos** | `GET .../files`, `GET/PATCH .../files/{filename}`, `GET .../download` |
| **Credenciales** | `GET/PUT /credentials`, `GET /credentials/detailed`, `DELETE /credentials/{provider}/{key_name}` |
| **Integraciones** | `GET /integrations`, `PATCH /integrations/{id}/token`, `GET/POST/DELETE /projects/{id}/integrations`, `POST /projects/{id}/integrations/link` |
| **Jira / HUs** | `GET/POST /jira/tickets`, `POST /jira/tickets/{issue_key}`, `GET /projects/{id}/user-stories`, `POST /projects/{id}/user-stories/sync` |
| **WebSocket** | `WS /ws/executions/{id}?token=<JWT>` |
| **Salud** | `GET /health` |

---

## Gotchas y troubleshooting

- **El worker Celery NO recarga solo.** Uvicorn corre con `--reload`, pero Celery
  no: tras cambiar código del backend, **reinicia el worker** (o usa `dev.sh`,
  que lo gestiona).
- **Generar tests requiere Gemini.** Sin `GOOGLE_API_KEY` (o credencial de IA por
  usuario), la ejecución termina en `failed` con un mensaje accionable. La key se
  resuelve: `GOOGLE_API_KEY` (env) → credencial del usuario (`provider=gemini`,
  `key_name=api_key`).
- **`ENCRYPTION_KEY` debe ser estable.** Si la rotas, las credenciales cifradas
  con la clave anterior dejan de poder descifrarse (`InvalidTag`).
- **Migraciones vs `create_all`.** En producción el esquema lo gestiona **solo
  Alembic** (`alembic upgrade head`). `create_all` al arrancar está limitado a
  entornos no productivos.
- **Postgres, no SQLite, en dev real.** Aunque `aiosqlite` está disponible (lo
  usan los tests), el desarrollo y la producción usan PostgreSQL.
- **CORS.** En producción añade el dominio del frontend a `ALLOWED_ORIGINS`.
- **`PYTHONPATH=.`** es necesario al invocar `uvicorn`/`celery`/`alembic` a mano
  (el paquete `backend` se resuelve desde la raíz). `dev.sh` ya lo exporta.

---

## Frontend

El frontend (React + Vite + TypeScript + Tailwind) está en el repositorio
**`qa-assistant-frontend`**. Para desarrollo local apunta su `.env.local` a este
backend:

```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```
