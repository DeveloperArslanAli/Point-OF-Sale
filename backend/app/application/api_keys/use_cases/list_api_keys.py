"""List API Keys use case."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.application.api_keys.ports import ApiKeyRepository
from app.domain.api_keys.entities import ApiKey


@dataclass(frozen=True, slots=True)
class ListApiKeysQuery:
    """Query to list API keys."""
    
    page: int = 1
    page_size: int = 50
    include_revoked: bool = False


@dataclass(frozen=True, slots=True)
class ListApiKeysResult:
    """Result of API key listing."""
    
    items: Sequence[ApiKey]
    total: int
    page: int
    page_size: int


class ListApiKeysUseCase:
    """Use case for listing API keys."""

    def __init__(self, repository: ApiKeyRepository) -> None:
        self._repo = repository

    async def execute(self, query: ListApiKeysQuery) -> ListApiKeysResult:
        """List API keys with pagination."""
        offset = (query.page - 1) * query.page_size
        items, total = await self._repo.list_all(
            offset=offset,
            limit=query.page_size,
            include_revoked=query.include_revoked,
        )

        return ListApiKeysResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
