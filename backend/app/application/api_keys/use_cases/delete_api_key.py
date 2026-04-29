"""Delete API Key use case."""
from __future__ import annotations

from app.application.api_keys.ports import ApiKeyRepository
from app.domain.common.errors import NotFoundError


class DeleteApiKeyUseCase:
    """Use case for permanently deleting an API key."""

    def __init__(self, repository: ApiKeyRepository) -> None:
        self._repo = repository

    async def execute(self, api_key_id: str) -> None:
        """Delete an API key permanently."""
        # Verify it exists first
        api_key = await self._repo.get_by_id(api_key_id)
        if not api_key:
            raise NotFoundError(
                f"API key not found: {api_key_id}",
                code="api_key.not_found",
            )

        success = await self._repo.delete(api_key_id)
        if not success:
            raise NotFoundError(
                f"Failed to delete API key: {api_key_id}",
                code="api_key.delete_failed",
            )
