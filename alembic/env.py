"""
Alembic environment — supports both offline and online migration modes.

Usage (once GCP credentials are provided):
  # Generate initial migration from models:
  alembic revision --autogenerate -m "initial schema"

  # Apply to GCP Cloud SQL:
  DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/qa_assistant alembic upgrade head
"""
import os
import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure project root is importable (so 'backend' package resolves)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import all models so Alembic detects schema changes automatically
from backend.models.db import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    """
    Returns the sync DB URL for Alembic.
    Uses settings.sync_database_url (reads from .env automatically).
    Falls back to sqlite for offline/CI use.
    """
    from backend.config import settings
    if settings.database_url:
        return settings.sync_database_url
    return config.get_main_option("sqlalchemy.url", "sqlite:///./qa_assistant.db")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _sync_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
