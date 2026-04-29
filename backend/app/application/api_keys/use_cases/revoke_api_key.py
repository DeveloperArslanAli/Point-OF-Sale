"""Revoke API Key use case."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.api_keys.ports import ApiKeyRepository
from app.domain.common.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class RevokeApiKeyCommand:
    """Command to revoke an API key."""
    
    api_key_id: str
    revoked_by: str


class RevokeApiKeyUseCase:
    """Use case for revoking API keys."""

    def __init__(self, repository: ApiKeyRepository) -> None:
        self._repo = repository

    async def execute(self, command: RevokeApiKeyCommand) -> None:
        """Revoke an API key."""
        api_key = await self._repo.get_by_id(command.api_key_id)
        if not api_key:
            raise NotFoundError(
                f"API key not found: {command.api_key_id}",
                code="api_key.not_found",
            )

        expected_version = api_key.version
        api_key.revoke(command.revoked_by)

        success = await self._repo.update(api_key, expected_version)
        if not success:
            raise NotFoundError(
                "Failed to update API key (concurrent modification)",
                code="api_key.update_conflict",
            )
