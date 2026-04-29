from __future__ import annotations

from logging.config import fileConfig
from typing import Any, MutableMapping

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.settings import get_settings
from app.infrastructure.db.models import (
    product_model,  # noqa: F401 ensure product table metadata loaded
    tenant_model,
    subscription_plan_model,
    supplier_ranking_weights_model,  # noqa: F401 supplier ranking weights
)
from app.infrastructure.db.models.auth import (
    user_model,  # noqa: F401 ensure user table metadata loaded
)
from app.infrastructure.db.session import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:  # pragma: no cover
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def _sync_database_url() -> str:
    """Translate async URLs into their synchronous counterpart for Alembic."""
    settings = get_settings()
    url = settings.DATABASE_URL
    if url.startswith("sqlite+aiosqlite"):
        return url.replace("sqlite+aiosqlite", "sqlite")
    if url.startswith("postgresql+asyncpg"):
        return url.replace("+asyncpg", "")
    return url


def run_migrations_offline() -> None:  # pragma: no cover - alembic generated style
    url = _sync_database_url()
    config.set_main_option("sqlalchemy.url", url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:  # pragma: no cover
    # Use a synchronous engine even though app runtime is async.
    # For SQLite URL we strip aiosqlite driver so Alembic can operate synchronously.
    section: MutableMapping[str, Any] = config.get_section(config.config_ini_section) or {}
    sync_url = _sync_database_url()
    section["sqlalchemy.url"] = sync_url
    section_dict: dict[str, Any] = dict(section)
    connectable = engine_from_config(section_dict, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():  # pragma: no cover
    run_migrations_offline()
else:  # pragma: no cover
    run_migrations_online()
