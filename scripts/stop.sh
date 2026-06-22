#!/usr/bin/env bash
#
# stop.sh — Detiene los servicios del backend.
#
# Por defecto detiene FastAPI + Celery (los servicios que arranca dev.sh).
# Pasa --all para también detener Redis y PostgreSQL.
#
# Uso:
#   ./scripts/stop.sh         # detiene FastAPI + Celery
#   ./scripts/stop.sh --all   # detiene además Redis + Postgres
#
set -euo pipefail

PG_DATA_DIR="$HOME/Library/Application Support/Postgres/var-18"
PG_BIN="/Applications/Postgres.app/Contents/Versions/18/bin"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RESET='\033[0m'

ok()   { printf "${GREEN}✓${RESET} %s\n" "$*"; }
warn() { printf "${YELLOW}!${RESET} %s\n" "$*"; }
log()  { printf "${BLUE}▶${RESET} %s\n" "$*"; }

# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------
if lsof -ti :8000 >/dev/null 2>&1; then
  lsof -ti :8000 | xargs kill -9 2>/dev/null || true
  ok "FastAPI detenido (:8000)"
else
  warn "FastAPI no estaba corriendo"
fi

# ---------------------------------------------------------------------------
# Celery worker (master + N children por --concurrency)
# Hacemos 2 pasadas: SIGTERM (gracia 2s) y luego SIGKILL a los que sobrevivan.
# ---------------------------------------------------------------------------
if pgrep -f "celery -A backend" >/dev/null 2>&1; then
  pkill -TERM -f "celery -A backend" 2>/dev/null || true
  sleep 2
  if pgrep -f "celery -A backend" >/dev/null 2>&1; then
    pkill -KILL -f "celery -A backend" 2>/dev/null || true
    warn "Celery forzado con SIGKILL (los workers no respondieron a SIGTERM)"
  fi
  # Verifica
  if pgrep -f "celery -A backend" >/dev/null 2>&1; then
    err "Celery aún vivo: $(pgrep -f 'celery -A backend' | tr '\n' ' ')"
  else
    ok "Celery worker (master + childs) detenido"
  fi
else
  warn "Celery no estaba corriendo"
fi

# ---------------------------------------------------------------------------
# Modo --all: también Redis + Postgres
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--all" ]]; then
  log "Modo --all: deteniendo también Redis y PostgreSQL"

  if redis-cli ping >/dev/null 2>&1; then
    redis-cli shutdown nosave 2>/dev/null || true
    ok "Redis detenido"
  else
    warn "Redis no estaba corriendo"
  fi

  if [[ -x "$PG_BIN/pg_ctl" ]] && "$PG_BIN/pg_ctl" -D "$PG_DATA_DIR" status >/dev/null 2>&1; then
    "$PG_BIN/pg_ctl" -D "$PG_DATA_DIR" stop -m fast >/dev/null 2>&1 || true
    ok "PostgreSQL detenido"
  else
    warn "PostgreSQL no estaba corriendo (o no encontré pg_ctl)"
  fi
fi

echo
ok "Listo."
