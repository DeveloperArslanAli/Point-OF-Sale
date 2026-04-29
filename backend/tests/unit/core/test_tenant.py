"""Tests for multi-tenant functionality."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from contextvars import Token

from app.core.tenant import (
    get_current_tenant_id,
    get_current_user_id,
    set_tenant_context,
    reset_tenant_context,
    set_user_context,
    reset_user_context,
    require_tenant,
    TenantAwareRepository,
)


class TestTenantContext:
    """Tests for tenant context management."""

    def test_get_current_tenant_id_default_none(self):
        """Test default tenant is None."""
        # Clear any existing context
        token = set_tenant_context(None)
        try:
            assert get_current_tenant_id() is None
        finally:
            reset_tenant_context(token)

    def test_set_and_get_tenant_id(self):
        """Test setting and getting tenant ID."""
        token = set_tenant_context("test_tenant_123")
        try:
            assert get_current_tenant_id() == "test_tenant_123"
        finally:
            reset_tenant_context(token)

    def test_reset_tenant_context(self):
        """Test resetting tenant context."""
        # Set initial value
        token1 = set_tenant_context("initial_tenant")
        
        # Set new value
        token2 = set_tenant_context("new_tenant")
        assert get_current_tenant_id() == "new_tenant"
        
        # Reset to previous value
        reset_tenant_context(token2)
        assert get_current_tenant_id() == "initial_tenant"
        
        # Cleanup
        reset_tenant_context(token1)

    def test_user_context(self):
        """Test user context management."""
        token = set_user_context("user_123")
        try:
            assert get_current_user_id() == "user_123"
        finally:
            reset_user_context(token)


class TestRequireTenant:
    """Tests for require_tenant dependency."""

    def test_require_tenant_raises_when_no_context(self):
        """Test require_tenant raises when no tenant set."""
        from app.domain.common.errors import UnauthorizedError
        
        token = set_tenant_context(None)
        try:
            dependency = require_tenant()
            with pytest.raises(UnauthorizedError, match="Tenant context required"):
                dependency()
        finally:
            reset_tenant_context(token)

    def test_require_tenant_returns_tenant_id(self):
        """Test require_tenant returns tenant ID when set."""
        token = set_tenant_context("tenant_abc")
        try:
            dependency = require_tenant()
            result = dependency()
            assert result == "tenant_abc"
        finally:
            reset_tenant_context(token)


class TestTenantAwareRepository:
    """Tests for TenantAwareRepository base class."""

    def test_apply_tenant_filter_with_context(self):
        """Test _apply_tenant_filter adds WHERE clause when tenant set."""
        # Create mock model class with tenant_id
        mock_model = MagicMock()
        mock_model.tenant_id = "column"
        
        # Create mock query
        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        
        repo = TenantAwareRepository()
        
        token = set_tenant_context("test_tenant")
        try:
            result = repo._apply_tenant_filter(mock_query, mock_model)
            mock_query.where.assert_called_once()
        finally:
            reset_tenant_context(token)

    def test_apply_tenant_filter_without_context(self):
        """Test _apply_tenant_filter returns unmodified query when no tenant."""
        mock_model = MagicMock()
        mock_query = MagicMock()
        
        repo = TenantAwareRepository()
        
        token = set_tenant_context(None)
        try:
            result = repo._apply_tenant_filter(mock_query, mock_model)
            # Query should be returned unmodified
            mock_query.where.assert_not_called()
            assert result == mock_query
        finally:
            reset_tenant_context(token)

    def test_get_tenant_id(self):
        """Test _get_tenant_id returns current tenant."""
        repo = TenantAwareRepository()
        
        token = set_tenant_context("my_tenant")
        try:
            assert repo._get_tenant_id() == "my_tenant"
        finally:
            reset_tenant_context(token)


class TestTenantIsolation:
    """Integration tests for tenant isolation in repositories."""

    def test_tenant_context_isolation_between_requests(self):
        """Test tenant context is isolated per execution context."""
        # Simulate request 1
        token1 = set_tenant_context("tenant_a")
        tenant_in_request1 = get_current_tenant_id()
        reset_tenant_context(token1)
        
        # Simulate request 2
        token2 = set_tenant_context("tenant_b")
        tenant_in_request2 = get_current_tenant_id()
        reset_tenant_context(token2)
        
        assert tenant_in_request1 == "tenant_a"
        assert tenant_in_request2 == "tenant_b"

    def test_nested_tenant_context(self):
        """Test nested tenant context handling."""
        token1 = set_tenant_context("outer_tenant")
        assert get_current_tenant_id() == "outer_tenant"
        
        token2 = set_tenant_context("inner_tenant")
        assert get_current_tenant_id() == "inner_tenant"
        
        reset_tenant_context(token2)
        assert get_current_tenant_id() == "outer_tenant"
        
        reset_tenant_context(token1)
