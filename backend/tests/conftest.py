import os
import sys

os.environ.setdefault("POS_DB_DISABLE_POOLING", "1")
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure backend root (directory containing 'app') is on path
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.infrastructure.db.session import async_session_factory  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    """Apply Alembic migrations once for the test session.

    This ensures required tables (products, users, etc.) exist because the
    runtime no longer auto-creates metadata and relies on migrations.
    """
    from alembic import command
    from alembic.config import Config

    # BACKEND_ROOT currently points to tests/.. (backend directory). Ensure we point to backend root explicitly.
    backend_root = BACKEND_ROOT  # already backend path
    alembic_ini = os.path.join(backend_root, "alembic.ini")
    cfg = Config(alembic_ini)
    # Ensure script_location resolves regardless of current working directory
    cfg.set_main_option("script_location", os.path.join(backend_root, "alembic"))
    # Run migrations to latest head
    command.upgrade(cfg, "head")


# Use pytest-asyncio to expose async-aware fixtures.
@pytest_asyncio.fixture()
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
