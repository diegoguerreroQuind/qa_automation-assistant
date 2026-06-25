# Despliegue de la base de datos — PostgreSQL en Cloud SQL (GCP)

Alcance: **solo la base de datos**. No cubre backend, frontend, Redis ni otra
infraestructura.

Artefactos en este directorio:
- [`schema.sql`](schema.sql) — DDL completo (tablas, índices, restricciones) +
  sello de Alembic. Validado contra PostgreSQL real.

> **Mitigaciones de riesgo aplicadas al esquema** (migración `e5f6a7b8c9d0`):
> 1. Se añadieron las 3 tablas que la cadena de migraciones histórica NO creaba
>    (`integrations`, `integration_secrets`, `project_integrations`) — antes un
>    `alembic upgrade head` limpio dejaba la BD incompleta.
> 2. **DEFAULTs a nivel de BD** en `role`, `status`, contadores, `selected`,
>    timestamps, etc. → inserciones manuales seguras.
> 3. **`ON DELETE CASCADE`** (y `SET NULL` en `executions.jira_issue_id`) en las
>    FKs, acorde a las cascadas del ORM → integridad de borrado en la BD.
> Verificado: `schema.sql` y `alembic upgrade head` producen esquemas idénticos.

---

## 0. Decisión previa: ¿`alembic upgrade head` o `schema.sql`?

| Camino | Cuándo usarlo |
|---|---|
| **`alembic upgrade head`** (recomendado) | Si puedes conectar la app/Alembic a Cloud SQL. Es el mecanismo canónico, idempotente, y registra `alembic_version`. **Las migraciones de este proyecto solo corren en modo *online*** (usan introspección en runtime); `--sql` offline NO funciona. |
| **`schema.sql`** | Despliegue dirigido por DBA, sin ejecutar la app. Aplica el esquema y **sella** `alembic_version` en el head `e5f6a7b8c9d0`, de modo que migraciones futuras sigan funcionando. |

> No mezcles ambos sobre la misma BD. Si aplicas `schema.sql`, las migraciones
> ya existentes quedan selladas como aplicadas.

---

## 1. Provisionar la instancia Cloud SQL

```bash
# Variables
export PROJECT_ID=tu-proyecto
export REGION=us-central1
export INSTANCE=qa-assistant-pg
export DB_NAME=qa_assistant

# Instancia PostgreSQL 16 (ajusta tier/almacenamiento a tu carga)
gcloud sql instances create "$INSTANCE" \
  --project="$PROJECT_ID" \
  --database-version=POSTGRES_16 \
  --region="$REGION" \
  --tier=db-custom-1-3840 \
  --storage-type=SSD --storage-size=10GB --storage-auto-increase \
  --backup --enable-point-in-time-recovery \
  --maintenance-window-day=SUN --maintenance-window-hour=6

# Base de datos (UTF-8 por defecto)
gcloud sql databases create "$DB_NAME" --instance="$INSTANCE"
```

### Usuarios (recomendado: dos roles)

```bash
# Usuario de migraciones (DDL) — corre Alembic / aplica schema.sql
gcloud sql users create qa_migrator --instance="$INSTANCE" --password='<MIGRATOR_PWD>'

# Usuario de aplicación (runtime, sin DDL)
gcloud sql users create qa_app --instance="$INSTANCE" --password='<APP_PWD>'
```

> Mínimo viable: un solo usuario que sea dueño del esquema. La separación
> migrator/app es la práctica de mínimo privilegio recomendada.

---

## 2. Conectarse de forma segura (Cloud SQL Auth Proxy)

```bash
# Descarga el proxy (https://cloud.google.com/sql/docs/postgres/sql-proxy)
./cloud-sql-proxy "$PROJECT_ID:$REGION:$INSTANCE" --port 5432 &
# Ahora Cloud SQL responde en localhost:5432
```

Alternativa: **IP privada + VPC** (sin exponer IP pública). Evita IP pública
abierta a 0.0.0.0/0.

---

## 3. Aplicar el esquema

### Opción A — Alembic (recomendado)

```bash
# .env apuntando al proxy:
#   DATABASE_URL=postgresql+asyncpg://qa_migrator:<MIGRATOR_PWD>@localhost:5432/qa_assistant
PYTHONPATH=. ./venv/bin/alembic upgrade head
```

### Opción B — schema.sql

```bash
psql "host=localhost port=5432 dbname=qa_assistant user=qa_migrator" \
     -v ON_ERROR_STOP=1 -f docs/db/schema.sql
```

---

## 4. Permisos del usuario de aplicación (mínimo privilegio)

Tras crear las tablas (con `qa_migrator`), otorga solo DML a `qa_app`:

```sql
-- Conectado a qa_assistant como qa_migrator (dueño del esquema)
GRANT USAGE ON SCHEMA public TO qa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO qa_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO qa_app;  -- columnas SERIAL

-- Que las tablas/secuencias futuras hereden los permisos
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO qa_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO qa_app;
```

El backend en runtime usa `qa_app`; Alembic usa `qa_migrator`.

---

## 5. Verificación post-despliegue

```sql
\dt                                  -- 10 tablas + alembic_version
SELECT version_num FROM alembic_version;   -- e5f6a7b8c9d0
SELECT count(*) FROM pg_indexes WHERE schemaname='public';  -- 28
```

---

## 6. Datos base (seed)

**No hay datos obligatorios**: el esquema funciona vacío y los usuarios se
registran por la API (`POST /auth/register`, rol `qa` por defecto).

### Crear el primer administrador

Recomendado (sin manipular hashes): registrar por la API y promover por SQL.

```sql
UPDATE users SET role = 'admin' WHERE email = 'admin@quind.io';
```

Alternativa por SQL directo (requiere generar el hash bcrypt con la app). La BD
ya aplica defaults para `role` y `created_at`; basta con dar `id` + columnas de
negocio:

```bash
# Genera el hash bcrypt con el mismo algoritmo del backend
python3 -c "import bcrypt; print(bcrypt.hashpw(b'TU_PASSWORD', bcrypt.gensalt()).decode())"
```

```sql
-- role se pasa explícito ('admin') porque el default es 'qa'; created_at usa now() por defecto
INSERT INTO users (id, email, name, hashed_password, role)
VALUES (gen_random_uuid()::text, 'admin@quind.io', 'Admin',
        '<HASH_BCRYPT_GENERADO>', 'admin');
```

> `gen_random_uuid()` está disponible en PostgreSQL 13+ sin extensiones.

---

## 7. Recomendaciones de operación

- **Backups + PITR** habilitados (ver paso 1). Define la ventana de retención.
- **`ENCRYPTION_KEY` fuera de la BD** (Secret Manager). Si se pierde, las
  credenciales cifradas (`credentials`, `integration_secrets`) son
  irrecuperables — la BD solo guarda texto cifrado.
- **No expongas IP pública** sin redes autorizadas/SSL; prefiere Auth Proxy o IP
  privada.
- **Una sola estrategia de esquema** (Alembic). Evita `create_all` en
  producción (la app ya lo desactiva cuando `ENVIRONMENT=production`).
