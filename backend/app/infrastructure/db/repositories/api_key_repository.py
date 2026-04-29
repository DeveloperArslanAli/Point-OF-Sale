"""API Key repository implementation."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import get_current_tenant_id
from app.domain.api_keys.entities import ApiKey, ApiKeyStatus
from app.infrastructure.db.models.api_key_model import ApiKeyModel


class SqlAlchemyApiKeyRepository:
    """Repository for API key persistence.
    
    Implements the ApiKeyRepository protocol from the application layer.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id and hasattr(ApiKeyModel, "tenant_id"):
            return stmt.where(ApiKeyModel.tenant_id == tenant_id)
        return stmt

    async def add(self, api_key: ApiKey) -> None:
        """Add a new API key."""
        tenant_id = get_current_tenant_id() or api_key.tenant_id
        model = ApiKeyModel(
            id=api_key.id,
            tenant_id=tenant_id,
            name=api_key.name,
            key_prefix=api_key.key_prefix,
            key_hash=api_key.key_hash,
            scopes=api_key.scopes,
            rate_limit_per_minute=api_key.rate_limit_per_minute,
            status=api_key.status.value,
            created_by=api_key.created_by,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            version=api_key.version,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_prefix(self, key_prefix: str) -> ApiKey | None:
        """Get API key by prefix (for lookup during auth)."""
        stmt = select(ApiKeyModel).where(ApiKeyModel.key_prefix == key_prefix)
        # Don't apply tenant filter - we need to find key first to get tenant
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id(self, key_id: str) -> ApiKey | None:
        """Get API key by ID."""
        stmt = select(ApiKeyModel).where(ApiKeyModel.id == key_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_keys(
        self,
        *,
        status: ApiKeyStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[ApiKey], int]:
        """List API keys for current tenant."""
        stmt = select(ApiKeyModel).order_by(ApiKeyModel.created_at.desc())
        count_stmt = select(func.count(ApiKeyModel.id))

        stmt = self._apply_tenant_filter(stmt)
        count_stmt = self._apply_tenant_filter(count_stmt)

        if status:
            stmt = stmt.where(ApiKeyModel.status == status.value)
            count_stmt = count_stmt.where(ApiKeyModel.status == status.value)

        stmt = stmt.offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        return [self._to_entity(m) for m in models], int(total)

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        include_revoked: bool = False,
    ) -> tuple[Sequence[ApiKey], int]:
        """List all API keys with pagination (Protocol method)."""
        status_filter = None if include_revoked else ApiKeyStatus.ACTIVE
        return await self.list_keys(status=status_filter, offset=offset, limit=limit)

        stmt = stmt.offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        return [self._to_entity(m) for m in models], int(total)

    async def update(self, api_key: ApiKey, expected_version: int | None = None) -> bool:
        """Update API key with optimistic locking."""
        version_check = expected_version if expected_version is not None else api_key.version - 1
        stmt = (
            update(ApiKeyModel)
            .where(
                ApiKeyModel.id == api_key.id,
                ApiKeyModel.version == version_check,
            )
            .values(
                status=api_key.status.value,
                last_used_at=api_key.last_used_at,
                revoked_at=api_key.revoked_at,
                revoked_by=api_key.revoked_by,
                version=api_key.version,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def delete(self, api_key_id: str) -> bool:
        """Hard delete an API key."""
        stmt = delete(ApiKeyModel).where(ApiKeyModel.id == api_key_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def count_active(self) -> int:
        """Count active API keys for the tenant."""
        stmt = select(func.count(ApiKeyModel.id)).where(
            ApiKeyModel.status == ApiKeyStatus.ACTIVE.value
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_key_hash(self, key_hash: str) -> ApiKey | None:
        """Get API key by its hash."""
        stmt = select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash)
        # Don't apply tenant filter - we need to find key first to get tenant
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def record_usage(self, key_id: str) -> None:
        """Record API key usage timestamp."""
        stmt = (
            update(ApiKeyModel)
            .where(ApiKeyModel.id == key_id)
            .values(last_used_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    def _to_entity(self, model: ApiKeyModel) -> ApiKey:
        """Convert model to entity."""
        return ApiKey(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            key_prefix=model.key_prefix,
            key_hash=model.key_hash,
            scopes=list(model.scopes or []),
            rate_limit_per_minute=model.rate_limit_per_minute,
            status=ApiKeyStatus(model.status),
            created_by=model.created_by,
            created_at=model.created_at,
            last_used_at=model.last_used_at,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            revoked_by=model.revoked_by,
            version=model.version,
        )


# Backward compatibility alias
ApiKeyRepository = SqlAlchemyApiKeyRepository
