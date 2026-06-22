#!/usr/bin/env bash
#
# dev.sh — Arranca el backend completo con un solo comando.
#
# Verifica/levanta:
#   1. PostgreSQL (Postgres.app)
#   2. Redis
#   3. FastAPI (uvicorn) en :8000
#   4. Celery worker
#
# Logs unificados en pantalla + archivos separados en /tmp/qa-*.log
# Ctrl+C detiene FastAPI y Celery limpiamente (Postgres y Redis quedan vivos).
#
# Uso:
#   ./scripts/dev.sh
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_BIN="$ROOT_DIR/venv/bin"
LOG_DIR="/tmp"
UVICORN_LOG="$LOG_DIR/qa-uvicorn.log"
CELERY_LOG="$LOG_DIR/qa-celery.log"

PG_DATA_DIR="$HOME/Library/Application Support/Postgres/var-18"
PG_BIN="/Applications/Postgres.app/Contents/Versions/18/bin"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RESET='\033[0m'

log()  { printf "${BLUE}▶${RESET} %s\n" "$*"; }
ok()   { printf "${GREEN}✓${RESET} %s\n" "$*"; }
warn() { printf "${YELLOW}!${RESET} %s\n" "$*"; }
err()  { printf "${RED}✗${RESET} %s\n" "$*" >&2; }

# ---------------------------------------------------------------------------
# Pre-checks
# ---------------------------------------------------------------------------
if [[ ! -d "$VENV_BIN" ]]; then
  err "No se encontró el venv en $VENV_BIN"
  err "Crea uno con: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ ! -f .env ]]; then
  err "Falta el archivo .env en la raíz del proyecto"
  exit 1
fi

# ---------------------------------------------------------------------------
# 1) PostgreSQL — local (Postgres.app)
# ---------------------------------------------------------------------------
log "Verificando PostgreSQL..."
if psql -h localhost -U "${USER}" -d qa_assistant -c "SELECT 1" >/dev/null 2>&1; then
  ok "PostgreSQL ya responde en :5432 (db qa_assistant)"
else
  warn "PostgreSQL no responde, intentando arrancar..."
  if [[ -x "$PG_BIN/pg_ctl" ]]; then
    "$PG_BIN/pg_ctl" -D "$PG_DATA_DIR" -l /tmp/qa-postgres.log start || true
    # Esperar hasta 10s a que esté listo
    for _ in $(seq 1 10); do
      if psql -h localhost -U "${USER}" -d qa_assistant -c "SELECT 1" >/dev/null 2>&1; then break; fi
      sleep 1
    done
    if psql -h localhost -U "${USER}" -d qa_assistant -c "SELECT 1" >/dev/null 2>&1; then
      ok "PostgreSQL arrancado"
    else
      err "No pude conectar a qa_assistant. Verifica Postgres.app o la DATABASE_URL en .env"
      exit 1
    fi
  else
    err "No encontré Postgres.app en $PG_BIN."
    err "Abre Postgres.app manualmente y vuelve a correr ./scripts/dev.sh"
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# 2) Redis
# ---------------------------------------------------------------------------
log "Verificando Redis..."
if redis-cli ping >/dev/null 2>&1; then
  ok "Redis ya responde en :6379"
else
  warn "Redis no responde, intentando arrancar..."
  if command -v redis-server >/dev/null 2>&1; then
    redis-server --daemonize yes --logfile /tmp/qa-redis.log >/dev/null
    sleep 1
    if redis-cli ping >/dev/null 2>&1; then
      ok "Redis arrancado en background"
    else
      err "No pude arrancar Redis"
      exit 1
    fi
  else
    err "redis-server no instalado. Instálalo con: brew install redis"
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# 3) Liberar puertos por si quedaron procesos colgados
# ---------------------------------------------------------------------------
if lsof -ti :8000 >/dev/null 2>&1; then
  warn "Puerto 8000 ocupado, liberando..."
  lsof -ti :8000 | xargs kill -9 2>/dev/null || true
  sleep 1
fi
pkill -f "celery.*backend.tasks" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 4) Migraciones Alembic (idempotente — no hace nada si ya está al día)
# ---------------------------------------------------------------------------
log "Aplicando migraciones Alembic..."
PYTHONPATH="$ROOT_DIR" "$VENV_BIN/alembic" upgrade head 2>&1 | grep -vE "^INFO" | tail -3 || true
ok "Migraciones al día"

# ---------------------------------------------------------------------------
# 5) FastAPI + Celery en background con cleanup automático
# ---------------------------------------------------------------------------
PIDS=()
cleanup() {
  echo
  log "Deteniendo backend..."

  # 1) Matar PIDs directos que guardamos
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done

  # 2) uvicorn --reload + celery lanzan hijos. SIGTERM, espera, luego SIGKILL.
  pkill -TERM -f "uvicorn backend.main:app" 2>/dev/null || true
  pkill -TERM -f "celery -A backend"        2>/dev/null || true
  sleep 2
  pkill -KILL -f "uvicorn backend.main:app" 2>/dev/null || true
  pkill -KILL -f "celery -A backend"        2>/dev/null || true

  # 3) Liberar puerto 8000 (por si algo queda colgado escuchando)
  if lsof -ti :8000 >/dev/null 2>&1; then
    lsof -ti :8000 | xargs kill -KILL 2>/dev/null || true
  fi

  # 4) Subprocesos directos de este shell
  pkill -P $$ 2>/dev/null || true

  ok "Detenido. Postgres y Redis siguen vivos (déjalos así o detenlos manualmente)."
  exit 0
}
trap cleanup INT TERM EXIT

log "Iniciando FastAPI (uvicorn) en :8000..."
PYTHONPATH="$ROOT_DIR" "$VENV_BIN/uvicorn" backend.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  > "$UVICORN_LOG" 2>&1 &
PIDS+=($!)

log "Iniciando Celery worker..."
PYTHONPATH="$ROOT_DIR" "$VENV_BIN/celery" -A backend.tasks.celery_app worker \
  --loglevel=info --concurrency=4 \
  > "$CELERY_LOG" 2>&1 &
PIDS+=($!)

# Esperar hasta 15s a que FastAPI responda
log "Esperando a que FastAPI responda..."
for _ in $(seq 1 15); do
  if curl -s http://localhost:8000/health >/dev/null 2>&1; then break; fi
  sleep 1
done

if curl -s http://localhost:8000/health >/dev/null 2>&1; then
  ok "FastAPI arriba: http://localhost:8000/health"
else
  err "FastAPI no responde. Revisa $UVICORN_LOG"
  cleanup
fi

echo
printf "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
printf "${GREEN}  Backend listo${RESET}\n"
printf "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
printf "  ${BLUE}API${RESET}     http://localhost:8000\n"
printf "  ${BLUE}Docs${RESET}    http://localhost:8000/docs\n"
printf "  ${BLUE}Logs${RESET}    $UVICORN_LOG\n"
printf "          $CELERY_LOG\n"
echo
printf "  ${YELLOW}Ctrl+C${RESET} para detener FastAPI + Celery (Postgres/Redis siguen).\n"
echo
printf "${BLUE}━━ logs en vivo (FastAPI + Celery mezclados) ━━${RESET}\n"

# Tail combinado con prefijos para distinguir origen
tail -F -n 0 "$UVICORN_LOG" "$CELERY_LOG" 2>/dev/null \
  | awk '/^==> .* <==$/{f=$2; next} { if (f ~ /uvicorn/) printf "\033[36m[api]\033[0m %s\n", $0; else printf "\033[35m[wrk]\033[0m %s\n", $0 }' &
PIDS+=($!)

# Esperar indefinidamente (hasta Ctrl+C)
wait
