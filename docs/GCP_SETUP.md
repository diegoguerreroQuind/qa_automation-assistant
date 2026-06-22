# Guía de Conexión a GCP Cloud SQL

## Paso 1 — Proveer credenciales

Una vez que tengas las credenciales de GCP, ejecuta los siguientes pasos:

### 1.1 Crear el archivo `.env`

```bash
cp .env.example .env
```

Completar en `.env`:

```env
# Cadena de conexión a Cloud SQL PostgreSQL
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/qa_assistant

# Generar claves de seguridad:
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
python3 -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_bytes(32).hex())"
```

## Paso 2 — Aplicar migraciones a GCP

Las migraciones crean todas las tablas en la base de datos de GCP.

```bash
source venv/bin/activate

# Exportar URL con driver SYNC (psycopg2) para Alembic
export DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/qa_assistant

# Aplicar todas las migraciones
alembic upgrade head
```

**Resultado esperado:**
```
INFO  [alembic.runtime.migration] Running upgrade  -> cf8b57388cb0, initial_schema
```

## Paso 3 — Verificar tablas creadas

Conectar a la base de datos y verificar:

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

**Tablas esperadas:**
- `alembic_version`
- `credentials`
- `endpoints`
- `executions`
- `generated_files`
- `projects`
- `users`

## Paso 4 — Levantar el backend

```bash
# Opción A — Desarrollo local (con venv)
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# En otra terminal — Celery worker
celery -A backend.tasks.celery_app worker --loglevel=info

# Opción B — Docker (Redis + Backend + Celery)
docker-compose up -d
```

## Paso 5 — Verificar

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"1.0.0","environment":"development"}

# Ver todos los endpoints en el navegador:
# http://localhost:8000/docs
```

## Opciones de Conexión GCP Cloud SQL

### A. Cloud SQL Auth Proxy (recomendado para producción)
```bash
# Descargar: https://cloud.google.com/sql/docs/postgres/connect-auth-proxy
./cloud-sql-proxy PROJECT:REGION:INSTANCE --port=5432
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/qa_assistant
```

### B. IP Pública con SSL
```env
DATABASE_URL=postgresql+asyncpg://user:pass@IP_PUBLICA:5432/qa_assistant?ssl=require
```

### C. IP Privada (VPC)
```env
DATABASE_URL=postgresql+asyncpg://user:pass@IP_PRIVADA:5432/qa_assistant
```

## Generar nuevas migraciones (cuando se modifiquen los modelos)

```bash
source venv/bin/activate
alembic revision --autogenerate -m "descripcion_del_cambio"
alembic upgrade head
```
