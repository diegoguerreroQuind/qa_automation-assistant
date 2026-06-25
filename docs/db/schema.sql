-- =============================================================================
-- QA AI Assistant — Esquema inicial PostgreSQL (Cloud SQL)
-- =============================================================================
-- Generado desde los modelos SQLAlchemy (backend/models/db.py), dialecto
-- PostgreSQL. Equivale al estado del head de Alembic: d4e5f6a7b8c9.
--
-- CAMINO CANÓNICO (recomendado):
--     alembic upgrade head      # online, contra Cloud SQL vía Auth Proxy
--   crea este mismo esquema Y registra alembic_version automáticamente.
--
-- USO DE ESTE SCRIPT (alternativa DBA / sin ejecutar la app):
--   Aplicar sobre una base de datos `qa_assistant` VACÍA. Al final se crea y
--   se sella la tabla alembic_version en el head, de modo que las migraciones
--   futuras (`alembic upgrade head`) sigan funcionando sin recrear tablas.
--
-- NOTAS DE DISEÑO (ver "Riesgos y decisiones" en la entrega):
--   * Los DEFAULTs de columnas viven en la APLICACIÓN, no en la BD. Toda
--     inserción manual debe especificar TODAS las columnas NOT NULL
--     (id, created_at, role, status, contadores, selected, ...).
--   * Las cascadas de borrado son a nivel ORM (no hay ON DELETE en las FKs).
--     Borrar filas padre por SQL directo fallará por violación de FK; el
--     borrado se hace desde la aplicación. Ver recomendación de ON DELETE.
--   * Los IDs UUID se almacenan como VARCHAR(36) y los genera la app.
--   * Las credenciales se guardan cifradas (AES-256-GCM) por la app; la BD solo
--     almacena el texto cifrado.
-- =============================================================================

BEGIN;

-- ----- Tipo enumerado de roles de usuario -----------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
        CREATE TYPE userrole AS ENUM ('admin', 'qa');
    END IF;
END$$;

-- ----- users ----------------------------------------------------------------
CREATE TABLE users (
    id              VARCHAR(36)              NOT NULL,
    email           VARCHAR(255)             NOT NULL,
    name            VARCHAR(255)             NOT NULL,
    hashed_password VARCHAR(255),
    role            userrole                 NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_email ON users (email);

-- ----- projects -------------------------------------------------------------
CREATE TABLE projects (
    id               VARCHAR(36)              NOT NULL,
    user_id          VARCHAR(36)              NOT NULL,
    name             VARCHAR(255)             NOT NULL,
    description      TEXT,
    jira_project_key VARCHAR(50),
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE INDEX ix_projects_user_id ON projects (user_id);

-- ----- credentials (legacy por-usuario; cifradas) ---------------------------
CREATE TABLE credentials (
    id              SERIAL                   NOT NULL,
    user_id         VARCHAR(36)              NOT NULL,
    provider        VARCHAR(20)              NOT NULL,
    key_name        VARCHAR(50)              NOT NULL,
    encrypted_value TEXT                     NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE INDEX ix_credentials_user_id ON credentials (user_id);

-- ----- integrations (credencial reutilizable del usuario) -------------------
CREATE TABLE integrations (
    id         VARCHAR(36)              NOT NULL,
    user_id    VARCHAR(36)              NOT NULL,
    provider   VARCHAR(20)              NOT NULL,
    name       VARCHAR(120)             NOT NULL,
    label      VARCHAR(255)             NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE INDEX ix_integrations_user_id ON integrations (user_id);

-- ----- jira_tickets (snapshot completo de la HU) ----------------------------
CREATE TABLE jira_tickets (
    id                  VARCHAR(36)              NOT NULL,
    user_id             VARCHAR(36)              NOT NULL,
    project_id          VARCHAR(36),
    issue_key           VARCHAR(50)              NOT NULL,
    summary             TEXT                     NOT NULL,
    description         TEXT,
    status              VARCHAR(100),
    assignee            VARCHAR(255),
    reporter            VARCHAR(255),
    sprint              VARCHAR(255),
    story_points        FLOAT,
    labels              TEXT,
    issue_type          VARCHAR(100),
    jira_created_at     VARCHAR(50),
    jira_updated_at     VARCHAR(50),
    raw_fields          TEXT,
    structured_criteria TEXT,
    fetched_at          TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_jira_project_issue UNIQUE (project_id, issue_key),
    FOREIGN KEY (user_id)    REFERENCES users (id),
    FOREIGN KEY (project_id) REFERENCES projects (id)
);
CREATE INDEX ix_jira_tickets_user_id    ON jira_tickets (user_id);
CREATE INDEX ix_jira_tickets_project_id ON jira_tickets (project_id);
CREATE INDEX ix_jira_tickets_issue_key  ON jira_tickets (issue_key);

-- ----- integration_secrets (valores cifrados de cada integración) -----------
CREATE TABLE integration_secrets (
    id              SERIAL      NOT NULL,
    integration_id  VARCHAR(36) NOT NULL,
    key_name        VARCHAR(50) NOT NULL,
    encrypted_value TEXT        NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_integration_key UNIQUE (integration_id, key_name),
    FOREIGN KEY (integration_id) REFERENCES integrations (id)
);
CREATE INDEX ix_integration_secrets_integration_id ON integration_secrets (integration_id);

-- ----- project_integrations (enlace proyecto ↔ credencial, 1 por proyecto) --
CREATE TABLE project_integrations (
    id             SERIAL                   NOT NULL,
    project_id     VARCHAR(36)              NOT NULL,
    integration_id VARCHAR(36)              NOT NULL,
    created_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_project_single_integration UNIQUE (project_id),
    FOREIGN KEY (project_id)     REFERENCES projects (id),
    FOREIGN KEY (integration_id) REFERENCES integrations (id)
);
CREATE INDEX ix_project_integrations_project_id     ON project_integrations (project_id);
CREATE INDEX ix_project_integrations_integration_id ON project_integrations (integration_id);

-- ----- executions -----------------------------------------------------------
CREATE TABLE executions (
    id                  VARCHAR(36)              NOT NULL,
    project_id          VARCHAR(36)              NOT NULL,
    jira_ticket_id      VARCHAR(50),
    jira_ticket_summary TEXT,
    jira_issue_id       VARCHAR(36),
    ai_model            VARCHAR(100)             NOT NULL,
    status              VARCHAR(20)              NOT NULL,
    endpoints_total     INTEGER                  NOT NULL,
    endpoints_selected  INTEGER                  NOT NULL,
    endpoints_generated INTEGER                  NOT NULL,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at        TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (project_id)    REFERENCES projects (id),
    FOREIGN KEY (jira_issue_id) REFERENCES jira_tickets (id)
);
CREATE INDEX ix_executions_project_id    ON executions (project_id);
CREATE INDEX ix_executions_jira_issue_id ON executions (jira_issue_id);

-- ----- endpoints ------------------------------------------------------------
CREATE TABLE endpoints (
    id            SERIAL       NOT NULL,
    execution_id  VARCHAR(36)  NOT NULL,
    name          VARCHAR(255) NOT NULL,
    method        VARCHAR(10)  NOT NULL,
    url           TEXT         NOT NULL,
    folder        VARCHAR(255),
    selected      BOOLEAN      NOT NULL,
    status        VARCHAR(20)  NOT NULL,
    error_message TEXT,
    headers       TEXT,
    body          TEXT,
    resolved_url  TEXT,
    variables     TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY (execution_id) REFERENCES executions (id)
);
CREATE INDEX ix_endpoints_execution_id ON endpoints (execution_id);

-- ----- generated_files ------------------------------------------------------
CREATE TABLE generated_files (
    id           SERIAL                   NOT NULL,
    execution_id VARCHAR(36)              NOT NULL,
    file_name    VARCHAR(255)             NOT NULL,
    file_type    VARCHAR(20)              NOT NULL,
    file_content TEXT                     NOT NULL,
    updated_at   TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (execution_id) REFERENCES executions (id)
);
CREATE INDEX ix_generated_files_execution_id ON generated_files (execution_id);

-- ----- Sellado de Alembic ---------------------------------------------------
-- Permite que `alembic upgrade head` reconozca el esquema como ya aplicado y
-- solo ejecute migraciones FUTURAS (evita el drift create_all vs Alembic).
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version (version_num) VALUES ('d4e5f6a7b8c9');

COMMIT;
