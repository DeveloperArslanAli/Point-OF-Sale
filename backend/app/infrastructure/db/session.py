from __future__ import annotations

from collections.abc import AsyncGenerator
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase

from app.core.settings import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()


def _use_null_pool() -> bool:
    """Return True when connection pooling should be disabled."""

    if os.getenv("POS_DB_DISABLE_POOLING") == "1":
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return True
    return getattr(_settings, "ENV", "dev") == "test"


pool_class = NullPool if _use_null_pool() else None
engine = create_async_engine(
    _settings.DATABASE_URL,
    echo=_settings.database_echo,
    poolclass=pool_class,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
# Export factory alias for tests
async_session_factory = AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:  # FastAPI dependency
    async with AsyncSessionLocal() as session:  # pragma: no cover - thin wrapper
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
