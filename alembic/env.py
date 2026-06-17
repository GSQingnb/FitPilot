"""Alembic env.py — async PostgreSQL support.

Loads DATABASE_URL from environment (Docker/CI) or project-root .env file.
Explicit environment variables take priority over .env (override=False).
"""
import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Load .env from project root ────────────────────────────────────────────
# __file__ = alembic/env.py → .parents[1] = project root
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DOTENV_PATH = _PROJECT_ROOT / ".env"
if _DOTENV_PATH.exists():
    load_dotenv(_DOTENV_PATH, override=False)

# Alembic Config object
config = context.config

# Override sqlalchemy.url from environment variable (set by Docker, CI, or .env)
env_url = os.getenv("DATABASE_URL", "")
if env_url:
    config.set_main_option("sqlalchemy.url", env_url)

# Warn if DATABASE_URL is not available at all
_url = config.get_main_option("sqlalchemy.url") or ""
if not _url:
    sys.exit(
        "ERROR: DATABASE_URL is not set. Set the environment variable or create a .env file.\n"
        f"  Expected .env at: {_DOTENV_PATH}\n"
        "  Or set: $env:DATABASE_URL = 'postgresql+asyncpg://user:pass@host:5432/db'"
    )

# Set up Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Alembic can detect them for autogenerate
from database.base import Base  # noqa: E402
import database.models  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — runs async loop."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
