"""
Webhook Event Publisher - Bridges domain events to webhook dispatch.

This module provides the infrastructure to publish domain events as webhooks
to external systems. It maps internal domain events to webhook event types
and triggers async dispatch via Celery.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from app.domain.common.events import DomainEvent
from app.domain.webhooks import WebhookEventType

logger = logging.getLogger(__name__)


# Mapping from domain event class names to webhook event types
DOMAIN_TO_WEBHOOK_EVENT_MAP: dict[str, WebhookEventType] = {
    # Sale events
    "SaleCreated": WebhookEventType.SALE_CREATED,
    "SaleCompleted": WebhookEventType.SALE_COMPLETED,
    "SaleVoided": WebhookEventType.SALE_VOIDED,
    # Inventory events
    "InventoryLowAlert": WebhookEventType.INVENTORY_LOW,
    "InventoryUpdated": WebhookEventType.INVENTORY_UPDATED,
    "InventoryReceived": WebhookEventType.INVENTORY_RECEIVED,
    "StockLevelChanged": WebhookEventType.INVENTORY_UPDATED,
    # Customer events
    "CustomerCreated": WebhookEventType.CUSTOMER_CREATED,
    "CustomerUpdated": WebhookEventType.CUSTOMER_UPDATED,
    "CustomerDeactivated": WebhookEventType.CUSTOMER_DEACTIVATED,
    # Product events
    "ProductCreated": WebhookEventType.PRODUCT_CREATED,
    "ProductUpdated": WebhookEventType.PRODUCT_UPDATED,
    "ProductDeleted": WebhookEventType.PRODUCT_DELETED,
    # Return events
    "ReturnCreated": WebhookEventType.RETURN_CREATED,
    "ReturnApproved": WebhookEventType.RETURN_APPROVED,
    "ReturnCompleted": WebhookEventType.RETURN_COMPLETED,
    # Employee events
    "EmployeeClockIn": WebhookEventType.EMPLOYEE_CLOCK_IN,
    "EmployeeClockOut": WebhookEventType.EMPLOYEE_CLOCK_OUT,
    # Loyalty events
    "LoyaltyPointsEarned": WebhookEventType.LOYALTY_POINTS_EARNED,
    "LoyaltyTierChanged": WebhookEventType.LOYALTY_TIER_CHANGED,
    # Gift card events
    "GiftCardCreated": WebhookEventType.GIFT_CARD_CREATED,
    "GiftCardRedeemed": WebhookEventType.GIFT_CARD_REDEEMED,
    # Order events
    "OrderCreated": WebhookEventType.ORDER_CREATED,
    "OrderShipped": WebhookEventType.ORDER_SHIPPED,
    "OrderDelivered": WebhookEventType.ORDER_DELIVERED,
}


class WebhookEventPublisher:
    """Publishes domain events as webhooks.
    
    This class is responsible for:
    1. Mapping domain events to webhook event types
    2. Serializing event payloads
    3. Triggering async webhook dispatch via Celery
    """

    def __init__(self, *, use_celery: bool = True) -> None:
        """Initialize the publisher.
        
        Args:
            use_celery: If True, dispatch via Celery tasks. If False, skip dispatch
                        (useful for testing or when Celery is disabled).
        """
        self._use_celery = use_celery

    def publish(
        self,
        event: DomainEvent,
        *,
        tenant_id: str | None = None,
    ) -> bool:
        """Publish a single domain event as a webhook.
        
        Args:
            event: The domain event to publish.
            tenant_id: The tenant ID for multi-tenant context.
            
        Returns:
            True if the event was queued for dispatch, False if it was skipped.
        """
        event_type = self._map_event_type(event)
        if event_type is None:
            logger.debug(
                "No webhook mapping for domain event %s",
                event.__class__.__name__,
            )
            return False

        payload = self._serialize_event(event)
        reference_id = event.aggregate_id

        return self._dispatch(
            event_type=event_type,
            payload=payload,
            reference_id=reference_id,
            tenant_id=tenant_id,
        )

    def publish_many(
        self,
        events: list[DomainEvent],
        *,
        tenant_id: str | None = None,
    ) -> int:
        """Publish multiple domain events.
        
        Args:
            events: List of domain events to publish.
            tenant_id: The tenant ID for multi-tenant context.
            
        Returns:
            Number of events successfully queued for dispatch.
        """
        count = 0
        for event in events:
            if self.publish(event, tenant_id=tenant_id):
                count += 1
        return count

    def publish_custom(
        self,
        event_type: WebhookEventType,
        payload: dict[str, Any],
        *,
        reference_id: str | None = None,
        tenant_id: str | None = None,
    ) -> bool:
        """Publish a custom webhook event (not from domain event).
        
        Useful for events that don't originate from domain aggregates.
        
        Args:
            event_type: The webhook event type to publish.
            payload: The event payload.
            reference_id: Optional reference ID for the event.
            tenant_id: The tenant ID for multi-tenant context.
            
        Returns:
            True if the event was queued for dispatch.
        """
        return self._dispatch(
            event_type=event_type,
            payload=payload,
            reference_id=reference_id,
            tenant_id=tenant_id,
        )

    def _map_event_type(self, event: DomainEvent) -> WebhookEventType | None:
        """Map a domain event to its corresponding webhook event type."""
        event_name = event.__class__.__name__
        return DOMAIN_TO_WEBHOOK_EVENT_MAP.get(event_name)

    def _serialize_event(self, event: DomainEvent) -> dict[str, Any]:
        """Serialize a domain event to a JSON-compatible dict."""
        try:
            data = asdict(event)
            # Convert datetime to ISO format strings
            for key, value in data.items():
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
            return data
        except Exception as e:
            logger.warning("Failed to serialize event %s: %s", event, e)
            # Fallback to basic serialization
            return {
                "event_id": event.event_id,
                "aggregate_id": event.aggregate_id,
                "occurred_at": event.occurred_at.isoformat(),
                "event_name": event.event_name,
            }

    def _dispatch(
        self,
        event_type: WebhookEventType,
        payload: dict[str, Any],
        *,
        reference_id: str | None = None,
        tenant_id: str | None = None,
    ) -> bool:
        """Dispatch the webhook event via Celery."""
        if not self._use_celery:
            logger.debug("Celery disabled, skipping webhook dispatch")
            return False

        try:
            from app.infrastructure.tasks.webhook_tasks import dispatch_webhook_event

            dispatch_webhook_event.delay(
                event_type=event_type.value,
                payload=payload,
                reference_id=reference_id,
                tenant_id=tenant_id,
            )
            logger.info(
                "Queued webhook event %s for dispatch (ref: %s)",
                event_type.value,
                reference_id,
            )
            return True
        except Exception as e:
            logger.error("Failed to queue webhook event: %s", e)
            return False


# Singleton instance for convenience
_publisher: WebhookEventPublisher | None = None


def get_webhook_publisher(*, use_celery: bool = True) -> WebhookEventPublisher:
    """Get the webhook event publisher singleton."""
    global _publisher
    if _publisher is None:
        _publisher = WebhookEventPublisher(use_celery=use_celery)
    return _publisher


def publish_domain_events(
    events: list[DomainEvent],
    *,
    tenant_id: str | None = None,
) -> int:
    """Convenience function to publish domain events as webhooks.
    
    This is the primary entry point for use cases to trigger webhook delivery
    after domain operations complete.
    
    Example usage in a use case:
        from app.infrastructure.webhooks.event_publisher import publish_domain_events
        
        async def execute(self) -> Sale:
            sale = Sale.create(...)
            await self._repo.add(sale)
            # Publish domain events as webhooks
            events = sale.pull_events()
            publish_domain_events(events, tenant_id=self._tenant_id)
            return sale
    
    Args:
        events: Domain events from an aggregate (typically from pull_events()).
        tenant_id: Tenant ID for multi-tenant context.
        
    Returns:
        Number of events successfully queued for webhook dispatch.
    """
    publisher = get_webhook_publisher()
    return publisher.publish_many(events, tenant_id=tenant_id)
