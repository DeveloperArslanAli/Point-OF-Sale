"""Tests for API key management."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from datetime import UTC, datetime, timedelta

from app.domain.api_keys.entities import ApiKey, ApiKeyScope, ApiKeyStatus
from app.api.dependencies.api_key_auth import generate_api_key, verify_api_key


class TestApiKeyEntity:
    """Tests for ApiKey entity."""

    def test_create_api_key(self):
        """Test creating an API key entity."""
        api_key = ApiKey(
            tenant_id="tenant123",
            name="Test Key",
            key_prefix="abcd1234",
            key_hash="hash",
            scopes=[ApiKeyScope.READ_PRODUCTS.value],
            created_by="user123",
        )
        
        assert api_key.tenant_id == "tenant123"
        assert api_key.name == "Test Key"
        assert api_key.status == ApiKeyStatus.ACTIVE
        assert api_key.is_valid()

    def test_api_key_is_valid_active(self):
        """Test valid active API key."""
        api_key = ApiKey(
            status=ApiKeyStatus.ACTIVE,
            expires_at=None,
        )
        assert api_key.is_valid()

    def test_api_key_is_invalid_revoked(self):
        """Test revoked API key is invalid."""
        api_key = ApiKey(
            status=ApiKeyStatus.REVOKED,
        )
        assert not api_key.is_valid()

    def test_api_key_is_invalid_expired(self):
        """Test expired API key is invalid."""
        api_key = ApiKey(
            status=ApiKeyStatus.ACTIVE,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert not api_key.is_valid()

    def test_api_key_is_valid_not_yet_expired(self):
        """Test API key that hasn't expired yet."""
        api_key = ApiKey(
            status=ApiKeyStatus.ACTIVE,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert api_key.is_valid()

    def test_has_scope_full_access(self):
        """Test full_access scope grants all scopes."""
        api_key = ApiKey(
            scopes=[ApiKeyScope.FULL_ACCESS.value],
        )
        assert api_key.has_scope("read:products")
        assert api_key.has_scope("write:sales")
        assert api_key.has_scope("any:scope")

    def test_has_scope_specific(self):
        """Test specific scope checking."""
        api_key = ApiKey(
            scopes=[ApiKeyScope.READ_PRODUCTS.value, ApiKeyScope.READ_INVENTORY.value],
        )
        assert api_key.has_scope("read:products")
        assert api_key.has_scope("read:inventory")
        assert not api_key.has_scope("write:products")

    def test_revoke_api_key(self):
        """Test revoking an API key."""
        api_key = ApiKey(
            status=ApiKeyStatus.ACTIVE,
            version=0,
        )
        
        api_key.revoke("admin123")
        
        assert api_key.status == ApiKeyStatus.REVOKED
        assert api_key.revoked_by == "admin123"
        assert api_key.revoked_at is not None
        assert api_key.version == 1

    def test_record_usage(self):
        """Test recording API key usage."""
        api_key = ApiKey()
        assert api_key.last_used_at is None
        
        api_key.record_usage()
        
        assert api_key.last_used_at is not None


class TestApiKeyGeneration:
    """Tests for API key generation and verification."""

    def test_generate_api_key_format(self):
        """Test generated API key has correct format."""
        full_key, key_prefix, key_hash = generate_api_key()
        
        # Check format: pos_live_XXXXXXXX.SECRET
        assert full_key.startswith("pos_live_")
        assert "." in full_key
        assert len(key_prefix) == 8
        assert len(key_hash) > 0

    def test_verify_api_key_success(self):
        """Test successful API key verification."""
        full_key, key_prefix, key_hash = generate_api_key()
        
        assert verify_api_key(full_key, key_hash)

    def test_verify_api_key_failure(self):
        """Test failed API key verification."""
        full_key, key_prefix, key_hash = generate_api_key()
        
        # Wrong key should fail
        assert not verify_api_key("pos_live_wrong.key", key_hash)

    def test_generate_api_key_unique(self):
        """Test that generated keys are unique."""
        key1 = generate_api_key()
        key2 = generate_api_key()
        
        assert key1[0] != key2[0]  # full keys different
        assert key1[1] != key2[1]  # prefixes different


class TestApiKeyScopes:
    """Tests for API key scopes enum."""

    def test_all_scopes_defined(self):
        """Test all expected scopes exist."""
        expected_scopes = [
            "read:products",
            "write:products",
            "read:inventory",
            "write:inventory",
            "read:sales",
            "write:sales",
            "read:customers",
            "write:customers",
            "read:reports",
            "webhooks",
            "full_access",
        ]
        
        actual_scopes = [s.value for s in ApiKeyScope]
        
        for scope in expected_scopes:
            assert scope in actual_scopes, f"Missing scope: {scope}"
