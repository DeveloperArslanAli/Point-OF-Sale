"""Create API Key use case."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.api_keys.ports import ApiKeyRepository
from app.domain.api_keys.entities import ApiKey, ApiKeyScope
from app.domain.common.errors import ValidationError


@dataclass(frozen=True, slots=True)
class CreateApiKeyCommand:
    """Command to create a new API key."""
    
    name: str
    scopes: list[str]
    rate_limit_per_minute: int
    created_by: str
    tenant_id: str
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CreateApiKeyResult:
    """Result of API key creation."""
    
    api_key: ApiKey
    raw_key: str  # Only available at creation time


class CreateApiKeyUseCase:
    """Use case for creating API keys."""

    def __init__(
        self,
        repository: ApiKeyRepository,
        *,
        hash_function: callable,
        generate_key_function: callable,
        max_keys_per_tenant: int = 50,
    ) -> None:
        self._repo = repository
        self._hash = hash_function
        self._generate_key = generate_key_function
        self._max_keys = max_keys_per_tenant

    async def execute(self, command: CreateApiKeyCommand) -> CreateApiKeyResult:
        """Create a new API key."""
        # Validate scopes
        valid_scopes = {s.value for s in ApiKeyScope}
        invalid = [s for s in command.scopes if s not in valid_scopes]
        if invalid:
            raise ValidationError(
                f"Invalid scopes: {invalid}",
                code="api_key.invalid_scopes",
            )

        # Check tenant limit
        active_count = await self._repo.count_active()
        if active_count >= self._max_keys:
            raise ValidationError(
                f"Maximum API keys ({self._max_keys}) reached for tenant",
                code="api_key.limit_exceeded",
            )

        # Generate the raw key and its hash
        raw_key = self._generate_key()
        key_prefix = raw_key[:8]
        key_hash = self._hash(raw_key)

        # Create entity
        api_key = ApiKey(
            tenant_id=command.tenant_id,
            name=command.name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=command.scopes,
            rate_limit_per_minute=command.rate_limit_per_minute,
            created_by=command.created_by,
            expires_at=command.expires_at,
        )

        await self._repo.add(api_key)

        return CreateApiKeyResult(api_key=api_key, raw_key=raw_key)
