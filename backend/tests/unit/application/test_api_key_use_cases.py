"""Unit tests for API key use cases."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Sequence
from unittest.mock import AsyncMock

import pytest

from app.application.api_keys.use_cases import (
    CreateApiKeyCommand,
    CreateApiKeyUseCase,
    DeleteApiKeyUseCase,
    GetApiKeyUseCase,
    ListApiKeysQuery,
    ListApiKeysUseCase,
    RevokeApiKeyCommand,
    RevokeApiKeyUseCase,
)
from app.domain.api_keys.entities import ApiKey, ApiKeyScope, ApiKeyStatus
from app.domain.common.errors import NotFoundError, ValidationError


class FakeApiKeyRepository:
    """In-memory fake repository for testing."""
    
    def __init__(self):
        self._keys: dict[str, ApiKey] = {}
        self._active_count = 0
    
    async def add(self, api_key: ApiKey) -> None:
        self._keys[api_key.id] = api_key
        self._active_count += 1
    
    async def get_by_id(self, api_key_id: str) -> ApiKey | None:
        return self._keys.get(api_key_id)
    
    async def get_by_key_hash(self, key_hash: str) -> ApiKey | None:
        for key in self._keys.values():
            if key.key_hash == key_hash:
                return key
        return None
    
    async def get_by_prefix(self, prefix: str) -> ApiKey | None:
        for key in self._keys.values():
            if key.key_prefix == prefix:
                return key
        return None
    
    async def update(self, api_key: ApiKey, expected_version: int) -> bool:
        if api_key.id not in self._keys:
            return False
        existing = self._keys[api_key.id]
        if existing.version != expected_version:
            return False
        self._keys[api_key.id] = api_key
        return True
    
    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        include_revoked: bool = False,
    ) -> tuple[Sequence[ApiKey], int]:
        items = list(self._keys.values())
        if not include_revoked:
            items = [k for k in items if k.status == ApiKeyStatus.ACTIVE]
        total = len(items)
        return items[offset:offset + limit], total
    
    async def delete(self, api_key_id: str) -> bool:
        if api_key_id in self._keys:
            del self._keys[api_key_id]
            return True
        return False
    
    async def count_active(self) -> int:
        return sum(1 for k in self._keys.values() if k.status == ApiKeyStatus.ACTIVE)


def fake_hash(value: str) -> str:
    """Fake hash function for testing."""
    return f"hashed:{value}"


def fake_generate_key() -> str:
    """Fake key generator for testing."""
    return "test-api-key-12345678901234567890"


class TestCreateApiKeyUseCase:
    """Tests for CreateApiKeyUseCase."""

    @pytest.fixture
    def repo(self):
        return FakeApiKeyRepository()

    @pytest.fixture
    def use_case(self, repo):
        return CreateApiKeyUseCase(
            repository=repo,
            hash_function=fake_hash,
            generate_key_function=fake_generate_key,
            max_keys_per_tenant=10,
        )

    @pytest.mark.asyncio
    async def test_create_api_key_success(self, use_case, repo):
        """Successfully create an API key."""
        command = CreateApiKeyCommand(
            name="Test Key",
            scopes=["read:products", "read:inventory"],
            rate_limit_per_minute=100,
            created_by="user-123",
            tenant_id="tenant-1",
        )
        
        result = await use_case.execute(command)
        
        assert result.raw_key == "test-api-key-12345678901234567890"
        assert result.api_key.name == "Test Key"
        assert result.api_key.key_prefix == "test-api"  # first 8 chars
        assert result.api_key.scopes == ["read:products", "read:inventory"]
        assert result.api_key.rate_limit_per_minute == 100
        assert len(repo._keys) == 1

    @pytest.mark.asyncio
    async def test_create_api_key_invalid_scope(self, use_case):
        """Invalid scopes should raise ValidationError."""
        command = CreateApiKeyCommand(
            name="Bad Key",
            scopes=["invalid:scope"],
            rate_limit_per_minute=60,
            created_by="user-123",
            tenant_id="tenant-1",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            await use_case.execute(command)
        
        assert "invalid:scope" in str(exc_info.value)
        assert exc_info.value.code == "api_key.invalid_scopes"

    @pytest.mark.asyncio
    async def test_create_api_key_exceeds_limit(self, repo):
        """Exceeding tenant limit should raise ValidationError."""
        use_case = CreateApiKeyUseCase(
            repository=repo,
            hash_function=fake_hash,
            generate_key_function=fake_generate_key,
            max_keys_per_tenant=2,
        )
        
        # Add 2 keys
        for i in range(2):
            await repo.add(ApiKey(
                id=f"key-{i}",
                tenant_id="tenant-1",
                name=f"Key {i}",
                key_prefix=f"prefix{i}",
                key_hash=f"hash{i}",
            ))
        
        command = CreateApiKeyCommand(
            name="Third Key",
            scopes=[],
            rate_limit_per_minute=60,
            created_by="user-123",
            tenant_id="tenant-1",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            await use_case.execute(command)
        
        assert exc_info.value.code == "api_key.limit_exceeded"


class TestRevokeApiKeyUseCase:
    """Tests for RevokeApiKeyUseCase."""

    @pytest.fixture
    def repo(self):
        return FakeApiKeyRepository()

    @pytest.mark.asyncio
    async def test_revoke_api_key_success(self, repo):
        """Successfully revoke an API key."""
        key = ApiKey(
            id="key-123",
            tenant_id="tenant-1",
            name="Test Key",
            key_prefix="testpref",
            key_hash="hash123",
        )
        await repo.add(key)
        
        use_case = RevokeApiKeyUseCase(repository=repo)
        command = RevokeApiKeyCommand(
            api_key_id="key-123",
            revoked_by="admin-1",
        )
        
        await use_case.execute(command)
        
        updated = await repo.get_by_id("key-123")
        assert updated.status == ApiKeyStatus.REVOKED
        assert updated.revoked_by == "admin-1"

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_key(self, repo):
        """Revoking nonexistent key should raise NotFoundError."""
        use_case = RevokeApiKeyUseCase(repository=repo)
        command = RevokeApiKeyCommand(
            api_key_id="nonexistent",
            revoked_by="admin-1",
        )
        
        with pytest.raises(NotFoundError) as exc_info:
            await use_case.execute(command)
        
        assert exc_info.value.code == "api_key.not_found"


class TestGetApiKeyUseCase:
    """Tests for GetApiKeyUseCase."""

    @pytest.fixture
    def repo(self):
        return FakeApiKeyRepository()

    @pytest.mark.asyncio
    async def test_get_api_key_success(self, repo):
        """Successfully get an API key by ID."""
        key = ApiKey(id="key-123", tenant_id="t1", name="Test")
        await repo.add(key)
        
        use_case = GetApiKeyUseCase(repository=repo)
        result = await use_case.execute("key-123")
        
        assert result.id == "key-123"
        assert result.name == "Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, repo):
        """Getting nonexistent key should raise NotFoundError."""
        use_case = GetApiKeyUseCase(repository=repo)
        
        with pytest.raises(NotFoundError):
            await use_case.execute("nonexistent")


class TestListApiKeysUseCase:
    """Tests for ListApiKeysUseCase."""

    @pytest.fixture
    def repo(self):
        return FakeApiKeyRepository()

    @pytest.mark.asyncio
    async def test_list_api_keys_empty(self, repo):
        """List with no keys returns empty result."""
        use_case = ListApiKeysUseCase(repository=repo)
        query = ListApiKeysQuery()
        
        result = await use_case.execute(query)
        
        assert result.items == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_list_api_keys_with_items(self, repo):
        """List returns all active keys."""
        await repo.add(ApiKey(id="k1", tenant_id="t1", name="Key 1"))
        await repo.add(ApiKey(id="k2", tenant_id="t1", name="Key 2"))
        
        use_case = ListApiKeysUseCase(repository=repo)
        result = await use_case.execute(ListApiKeysQuery())
        
        assert len(result.items) == 2
        assert result.total == 2

    @pytest.mark.asyncio
    async def test_list_api_keys_pagination(self, repo):
        """Pagination should work correctly."""
        for i in range(5):
            await repo.add(ApiKey(id=f"k{i}", tenant_id="t1", name=f"Key {i}"))
        
        use_case = ListApiKeysUseCase(repository=repo)
        result = await use_case.execute(ListApiKeysQuery(page=1, page_size=2))
        
        assert len(result.items) == 2
        assert result.total == 5
        assert result.page == 1
        assert result.page_size == 2


class TestDeleteApiKeyUseCase:
    """Tests for DeleteApiKeyUseCase."""

    @pytest.fixture
    def repo(self):
        return FakeApiKeyRepository()

    @pytest.mark.asyncio
    async def test_delete_api_key_success(self, repo):
        """Successfully delete an API key."""
        await repo.add(ApiKey(id="key-123", tenant_id="t1", name="Test"))
        
        use_case = DeleteApiKeyUseCase(repository=repo)
        await use_case.execute("key-123")
        
        assert await repo.get_by_id("key-123") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, repo):
        """Deleting nonexistent key should raise NotFoundError."""
        use_case = DeleteApiKeyUseCase(repository=repo)
        
        with pytest.raises(NotFoundError):
            await use_case.execute("nonexistent")
