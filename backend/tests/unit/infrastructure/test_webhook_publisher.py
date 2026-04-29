"""Unit tests for the webhook event publisher."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.domain.common.events import DomainEvent
from app.domain.common.identifiers import new_ulid
from app.domain.webhooks import WebhookEventType
from app.infrastructure.webhooks.event_publisher import (
    DOMAIN_TO_WEBHOOK_EVENT_MAP,
    WebhookEventPublisher,
    get_webhook_publisher,
    publish_domain_events,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SaleCreated(DomainEvent):
    """Test domain event for sale creation."""
    sale_total: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class UnmappedEvent(DomainEvent):
    """Event without webhook mapping."""
    data: str = ""


class TestWebhookEventPublisher:
    """Tests for WebhookEventPublisher."""

    def test_event_map_contains_expected_events(self):
        """Verify key domain events are mapped."""
        assert "SaleCreated" in DOMAIN_TO_WEBHOOK_EVENT_MAP
        assert "InventoryLowAlert" in DOMAIN_TO_WEBHOOK_EVENT_MAP
        assert "CustomerCreated" in DOMAIN_TO_WEBHOOK_EVENT_MAP
        assert "ProductUpdated" in DOMAIN_TO_WEBHOOK_EVENT_MAP

    def test_publish_without_celery_returns_false(self):
        """Publisher with Celery disabled should skip dispatch."""
        publisher = WebhookEventPublisher(use_celery=False)
        event = SaleCreated(aggregate_id="sale-123", sale_total=99.99)
        
        result = publisher.publish(event, tenant_id="tenant-1")
        
        assert result is False

    def test_publish_unmapped_event_returns_false(self):
        """Events without webhook mapping should be skipped."""
        publisher = WebhookEventPublisher(use_celery=True)
        event = UnmappedEvent(aggregate_id="agg-123", data="test")
        
        result = publisher.publish(event, tenant_id="tenant-1")
        
        assert result is False

    def test_map_event_type_returns_correct_type(self):
        """Verify event type mapping works correctly."""
        publisher = WebhookEventPublisher(use_celery=False)
        event = SaleCreated(aggregate_id="sale-123")
        
        event_type = publisher._map_event_type(event)
        
        assert event_type == WebhookEventType.SALE_CREATED

    def test_serialize_event_includes_all_fields(self):
        """Verify event serialization captures all fields."""
        publisher = WebhookEventPublisher(use_celery=False)
        event = SaleCreated(
            aggregate_id="sale-123",
            sale_total=99.99,
        )
        
        payload = publisher._serialize_event(event)
        
        assert payload["aggregate_id"] == "sale-123"
        assert payload["sale_total"] == 99.99
        assert "event_id" in payload
        assert "occurred_at" in payload

    def test_serialize_event_converts_datetime_to_iso(self):
        """Datetimes should be converted to ISO format strings."""
        publisher = WebhookEventPublisher(use_celery=False)
        event = SaleCreated(aggregate_id="sale-123")
        
        payload = publisher._serialize_event(event)
        
        # Should be a string, not a datetime object
        assert isinstance(payload["occurred_at"], str)
        assert "T" in payload["occurred_at"]  # ISO format

    @patch("app.infrastructure.webhooks.event_publisher.dispatch_webhook_event")
    def test_publish_queues_celery_task(self, mock_dispatch):
        """Verify Celery task is queued for valid events."""
        publisher = WebhookEventPublisher(use_celery=True)
        event = SaleCreated(aggregate_id="sale-123", sale_total=50.0)
        
        result = publisher.publish(event, tenant_id="tenant-1")
        
        assert result is True
        mock_dispatch.delay.assert_called_once()
        call_kwargs = mock_dispatch.delay.call_args.kwargs
        assert call_kwargs["event_type"] == "sale.created"
        assert call_kwargs["tenant_id"] == "tenant-1"
        assert call_kwargs["reference_id"] == "sale-123"

    def test_publish_many_counts_successful_dispatches(self):
        """Verify publish_many returns correct count."""
        publisher = WebhookEventPublisher(use_celery=False)
        events = [
            SaleCreated(aggregate_id="sale-1"),
            UnmappedEvent(aggregate_id="agg-2", data="x"),
            SaleCreated(aggregate_id="sale-3"),
        ]
        
        count = publisher.publish_many(events, tenant_id="tenant-1")
        
        # Both SaleCreated events would dispatch, UnmappedEvent skipped
        # But use_celery=False means all return False
        assert count == 0

    @patch("app.infrastructure.webhooks.event_publisher.dispatch_webhook_event")
    def test_publish_custom_dispatches_directly(self, mock_dispatch):
        """Verify custom events can be published without domain event."""
        publisher = WebhookEventPublisher(use_celery=True)
        
        result = publisher.publish_custom(
            event_type=WebhookEventType.INVENTORY_LOW,
            payload={"product_id": "prod-123", "current_stock": 5},
            reference_id="prod-123",
            tenant_id="tenant-1",
        )
        
        assert result is True
        mock_dispatch.delay.assert_called_once()


class TestPublishDomainEventsHelper:
    """Tests for the convenience function."""

    def test_get_webhook_publisher_returns_singleton(self):
        """Singleton should be returned."""
        # Reset singleton for test
        import app.infrastructure.webhooks.event_publisher as mod
        mod._publisher = None
        
        p1 = get_webhook_publisher(use_celery=False)
        p2 = get_webhook_publisher()
        
        assert p1 is p2

    @patch("app.infrastructure.webhooks.event_publisher.get_webhook_publisher")
    def test_publish_domain_events_delegates_to_publisher(self, mock_get):
        """Convenience function should delegate to publisher."""
        mock_publisher = MagicMock()
        mock_publisher.publish_many.return_value = 2
        mock_get.return_value = mock_publisher
        
        events = [SaleCreated(aggregate_id="s1"), SaleCreated(aggregate_id="s2")]
        result = publish_domain_events(events, tenant_id="t1")
        
        assert result == 2
        mock_publisher.publish_many.assert_called_once_with(events, tenant_id="t1")
