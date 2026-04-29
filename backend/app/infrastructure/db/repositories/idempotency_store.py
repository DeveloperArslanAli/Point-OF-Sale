"""Idempotency store implementations."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Dict, Tuple

from sqlalchemy import select, String, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.application.offline_sync import IIdempotencyStore
from app.infrastructure.db.session import Base


class IdempotencyKeyModel(Base):
    """SQLAlchemy model for idempotency keys."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    result_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SqlAlchemyIdempotencyStore(IIdempotencyStore):
    """SQLAlchemy-based idempotency store."""

    def __init__(
        self,
        session: AsyncSession,
        ttl_hours: int = 24,
    ) -> None:
        self._session = session
        self._ttl_hours = ttl_hours

    async def check_key(self, key: str) -> bool:
        """Check if key has been processed."""
        stmt = select(IdempotencyKeyModel).where(
            IdempotencyKeyModel.key == key,
            IdempotencyKeyModel.expires_at > datetime.now(UTC),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def store_key(self, key: str, result_id: str | None = None) -> None:
        """Store a processed key."""
        expires_at = datetime.now(UTC) + timedelta(hours=self._ttl_hours)
        model = IdempotencyKeyModel(
            key=key,
            result_id=result_id,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_result(self, key: str) -> str | None:
        """Get the result ID for a processed key."""
        stmt = select(IdempotencyKeyModel.result_id).where(
            IdempotencyKeyModel.key == key,
            IdempotencyKeyModel.expires_at > datetime.now(UTC),
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row


class InMemoryIdempotencyStore(IIdempotencyStore):
    """In-memory idempotency store for testing."""

    def __init__(self, ttl_hours: int = 24) -> None:
        self._store: Dict[str, Tuple[str | None, datetime]] = {}
        self._ttl_hours = ttl_hours

    async def check_key(self, key: str) -> bool:
        """Check if key has been processed."""
        if key not in self._store:
            return False
        _, expires_at = self._store[key]
        if expires_at < datetime.now(UTC):
            del self._store[key]
            return False
        return True

    async def store_key(self, key: str, result_id: str | None = None) -> None:
        """Store a processed key."""
        expires_at = datetime.now(UTC) + timedelta(hours=self._ttl_hours)
        self._store[key] = (result_id, expires_at)

    async def get_result(self, key: str) -> str | None:
        """Get the result ID for a processed key."""
        if key not in self._store:
            return None
        result_id, expires_at = self._store[key]
        if expires_at < datetime.now(UTC):
            del self._store[key]
            return None
        return result_id
