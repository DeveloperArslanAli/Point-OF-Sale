"""Tests for observability modules."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.infrastructure.observability.tracing import (
    get_tracer,
    create_span,
    trace_function,
    _NoOpTracer,
    _NoOpSpan,
    add_sale_attributes,
    add_inventory_attributes,
    add_tenant_attributes,
)
from app.infrastructure.observability.sentry import (
    set_user_context,
    set_tenant_context,
    add_breadcrumb,
    capture_message,
    capture_exception,
    set_tag,
)


class TestNoOpTracer:
    """Tests for NoOpTracer when OpenTelemetry is not available."""

    def test_no_op_tracer_context_manager(self):
        """Test NoOpTracer works as context manager."""
        tracer = _NoOpTracer()
        
        with tracer.start_as_current_span("test_span") as span:
            assert isinstance(span, _NoOpSpan)

    def test_no_op_span_methods(self):
        """Test NoOpSpan methods don't raise."""
        span = _NoOpSpan()
        
        # These should all be no-ops that don't raise
        span.set_attribute("key", "value")
        span.set_status("OK")
        span.record_exception(Exception("test"))
        span.add_event("test_event", {"attr": "value"})


class TestCreateSpan:
    """Tests for create_span helper."""

    def test_create_span_basic(self):
        """Test basic span creation."""
        with create_span("test_operation") as span:
            assert span is not None

    def test_create_span_with_attributes(self):
        """Test span creation with initial attributes."""
        attributes = {"user_id": "123", "action": "test"}
        
        with create_span("test_operation", attributes=attributes) as span:
            assert span is not None


class TestTraceFunctionDecorator:
    """Tests for trace_function decorator."""

    def test_trace_function_sync(self):
        """Test trace_function with sync function."""
        @trace_function("test_func")
        def sync_func(x: int) -> int:
            return x * 2
        
        result = sync_func(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_trace_function_async(self):
        """Test trace_function with async function."""
        @trace_function("test_async_func")
        async def async_func(x: int) -> int:
            return x * 2
        
        result = await async_func(5)
        assert result == 10

    def test_trace_function_exception_handling(self):
        """Test trace_function records exceptions."""
        @trace_function("failing_func")
        def failing_func():
            raise ValueError("test error")
        
        with pytest.raises(ValueError, match="test error"):
            failing_func()


class TestAttributeHelpers:
    """Tests for span attribute helper functions."""

    def test_add_sale_attributes(self):
        """Test adding sale attributes to span."""
        span = MagicMock()
        
        add_sale_attributes(span, "sale123", 99.99, 3)
        
        assert span.set_attribute.call_count == 3
        span.set_attribute.assert_any_call("sale.id", "sale123")
        span.set_attribute.assert_any_call("sale.total", 99.99)
        span.set_attribute.assert_any_call("sale.items_count", 3)

    def test_add_inventory_attributes(self):
        """Test adding inventory attributes to span."""
        span = MagicMock()
        
        add_inventory_attributes(span, "prod123", 50, "IN")
        
        assert span.set_attribute.call_count == 3
        span.set_attribute.assert_any_call("inventory.product_id", "prod123")
        span.set_attribute.assert_any_call("inventory.quantity", 50)
        span.set_attribute.assert_any_call("inventory.movement_type", "IN")

    def test_add_tenant_attributes(self):
        """Test adding tenant attributes to span."""
        span = MagicMock()
        
        add_tenant_attributes(span, "tenant123")
        
        span.set_attribute.assert_called_once_with("tenant.id", "tenant123")


class TestSentryHelpers:
    """Tests for Sentry helper functions (no-op when SDK not available)."""

    def test_set_user_context_no_sdk(self):
        """Test set_user_context doesn't raise when SDK not available."""
        # Should not raise even if Sentry is not installed
        set_user_context("user123", "user@example.com", "admin")

    def test_set_tenant_context_no_sdk(self):
        """Test set_tenant_context doesn't raise when SDK not available."""
        set_tenant_context("tenant123", "Test Tenant")

    def test_add_breadcrumb_no_sdk(self):
        """Test add_breadcrumb doesn't raise when SDK not available."""
        add_breadcrumb("User clicked button", category="ui", level="info")

    def test_capture_message_no_sdk(self):
        """Test capture_message returns None when SDK not available."""
        result = capture_message("Test message", level="info")
        assert result is None

    def test_capture_exception_no_sdk(self):
        """Test capture_exception returns None when SDK not available."""
        try:
            raise ValueError("test")
        except ValueError as e:
            result = capture_exception(e)
            assert result is None

    def test_set_tag_no_sdk(self):
        """Test set_tag doesn't raise when SDK not available."""
        set_tag("environment", "test")
