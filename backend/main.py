"""
QA AI Assistant — FastAPI Application Entry Point

Run locally:
    uvicorn backend.main:app --reload --port 8000

Run Celery worker (separate terminal):
    celery -A backend.tasks.celery_app worker --loglevel=info
"""
import logging
import time
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Logging — configure before any module uses the root logger.
# force=True overrides uvicorn's default handler so our format is used.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    force=True,
)
logger = logging.getLogger("qa_assistant.http")

from backend.config import settings
from backend.models.database import init_db
from backend.routers.auth import router as auth_router
from backend.routers.oauth import router as oauth_router
from backend.routers.credentials import router as credentials_router
from backend.routers.integrations import router as integrations_router
from backend.routers.executions import router as executions_router
from backend.routers.files import router as files_router
from backend.routers.jira import router as jira_router
from backend.routers.user_stories import router as user_stories_router
from backend.routers.projects import router as projects_router
from backend.routers.websocket import router as websocket_router
from backend.services.session_cleanup import cleanup_expired_sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables (safe for GCP Cloud SQL — creates only if missing)
    await init_db()

    # Schedule file-system cleanup every 6 hours (removes sessions older than TTL)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(cleanup_expired_sessions, "interval", hours=6, id="session_cleanup")
    scheduler.start()

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(
    title="QA AI Assistant API",
    description=(
        "Backend que orquesta el framework de automatización QA con IA. "
        "Convierte colecciones Postman + tickets Jira en proyectos Cypress BDD."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# El JWT viaja en el header Authorization (Bearer), no en cookies, por lo que
# allow_credentials debe ser False; eso además evita la combinación insegura de
# credenciales + wildcards. Métodos y headers se restringen explícitamente.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# HTTP logging middleware — logs every request with method, path, status, duration
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "%s %s → %s (%dms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Global error handler — ensures consistent JSON error shape
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    content = {"detail": "Error interno del servidor"}
    # El nombre del tipo de excepción filtra detalles de implementación; solo se
    # expone fuera de producción para facilitar el debugging local.
    if settings.environment != "production":
        content["type"] = type(exc).__name__
    return JSONResponse(status_code=500, content=content)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(oauth_router)
app.include_router(credentials_router)
app.include_router(integrations_router)
app.include_router(projects_router)
app.include_router(jira_router)
app.include_router(user_stories_router)
app.include_router(executions_router)
app.include_router(files_router)
app.include_router(websocket_router)


# ---------------------------------------------------------------------------
# Health check (used by Docker healthcheck and load balancers)
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "1.0.0", "environment": settings.environment}
