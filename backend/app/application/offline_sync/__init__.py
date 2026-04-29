"""Offline sync application ports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from app.domain.offline_sync import OfflineQueueItem


class IIdempotencyStore(ABC):
    """Store for tracking processed idempotency keys."""

    @abstractmethod
    async def check_key(self, key: str) -> bool:
        """Check if key has been processed. Returns True if exists."""
        ...

    @abstractmethod
    async def store_key(self, key: str, result_id: str | None = None) -> None:
        """Store a processed key with optional result ID."""
        ...

    @abstractmethod
    async def get_result(self, key: str) -> str | None:
        """Get the result ID for a processed key."""
        ...
