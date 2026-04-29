"""API Keys application layer ports (interfaces)."""
from __future__ import annotations

from abc import abstractmethod
from typing import Protocol, Sequence

from app.domain.api_keys.entities import ApiKey


class ApiKeyRepository(Protocol):
    """Port for API key persistence."""

    @abstractmethod
    async def add(self, api_key: ApiKey) -> None:
        """Add a new API key."""
        ...

    @abstractmethod
    async def get_by_id(self, api_key_id: str) -> ApiKey | None:
        """Get API key by ID."""
        ...

    @abstractmethod
    async def get_by_key_hash(self, key_hash: str) -> ApiKey | None:
        """Get API key by its hash."""
        ...

    @abstractmethod
    async def get_by_prefix(self, prefix: str) -> ApiKey | None:
        """Get API key by its prefix."""
        ...

    @abstractmethod
    async def update(self, api_key: ApiKey, expected_version: int) -> bool:
        """Update API key with optimistic locking."""
        ...

    @abstractmethod
    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        include_revoked: bool = False,
    ) -> tuple[Sequence[ApiKey], int]:
        """List all API keys with pagination."""
        ...

    @abstractmethod
    async def delete(self, api_key_id: str) -> bool:
        """Hard delete an API key."""
        ...

    @abstractmethod
    async def count_active(self) -> int:
        """Count active API keys for the tenant."""
        ...
