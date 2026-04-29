"""Get API Key use case."""
from __future__ import annotations

from app.application.api_keys.ports import ApiKeyRepository
from app.domain.api_keys.entities import ApiKey
from app.domain.common.errors import NotFoundError


class GetApiKeyUseCase:
    """Use case for retrieving a single API key."""

    def __init__(self, repository: ApiKeyRepository) -> None:
        self._repo = repository

    async def execute(self, api_key_id: str) -> ApiKey:
        """Get an API key by ID."""
        api_key = await self._repo.get_by_id(api_key_id)
        if not api_key:
            raise NotFoundError(
                f"API key not found: {api_key_id}",
                code="api_key.not_found",
            )
        return api_key
