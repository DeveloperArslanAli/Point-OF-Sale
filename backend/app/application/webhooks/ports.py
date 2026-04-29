"""Application layer ports for webhook system."""
from __future__ import annotations

from typing import Protocol, Sequence

from app.domain.webhooks import (
    DeliveryStatus,
    WebhookDelivery,
    WebhookEvent,
    WebhookEventType,
    WebhookSubscription,
)


class WebhookSubscriptionRepository(Protocol):
    """Repository protocol for webhook subscriptions."""

    async def add(self, subscription: WebhookSubscription) -> None:
        """Add a new webhook subscription."""
        ...  # pragma: no cover

    async def get_by_id(self, subscription_id: str) -> WebhookSubscription | None:
        """Get subscription by ID."""
        ...  # pragma: no cover

    async def get_by_name(self, name: str) -> WebhookSubscription | None:
        """Get subscription by name."""
        ...  # pragma: no cover

    async def update(
        self, subscription: WebhookSubscription, *, expected_version: int
    ) -> bool:
        """Update subscription with optimistic locking."""
        ...  # pragma: no cover

    async def delete(self, subscription_id: str) -> bool:
        """Delete a subscription."""
        ...  # pragma: no cover

    async def list_by_event(
        self, event_type: WebhookEventType
    ) -> Sequence[WebhookSubscription]:
        """List active subscriptions for an event type."""
        ...  # pragma: no cover

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[WebhookSubscription], int]:
        """List all subscriptions."""
        ...  # pragma: no cover


class WebhookEventRepository(Protocol):
    """Repository protocol for webhook events."""

    async def add(self, event: WebhookEvent) -> None:
        """Add a new webhook event."""
        ...  # pragma: no cover

    async def get_by_id(self, event_id: str) -> WebhookEvent | None:
        """Get event by ID."""
        ...  # pragma: no cover

    async def list_recent(
        self,
        *,
        event_type: WebhookEventType | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[WebhookEvent], int]:
        """List recent events."""
        ...  # pragma: no cover


class WebhookDeliveryRepository(Protocol):
    """Repository protocol for webhook deliveries."""

    async def add(self, delivery: WebhookDelivery) -> None:
        """Add a new delivery record."""
        ...  # pragma: no cover

    async def get_by_id(self, delivery_id: str) -> WebhookDelivery | None:
        """Get delivery by ID."""
        ...  # pragma: no cover

    async def update(self, delivery: WebhookDelivery) -> None:
        """Update a delivery record."""
        ...  # pragma: no cover

    async def list_pending_retries(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[WebhookDelivery]:
        """List deliveries pending retry."""
        ...  # pragma: no cover

    async def list_by_subscription(
        self,
        subscription_id: str,
        *,
        status: DeliveryStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[WebhookDelivery], int]:
        """List deliveries for a subscription."""
        ...  # pragma: no cover

    async def list_by_event(
        self,
        event_id: str,
    ) -> Sequence[WebhookDelivery]:
        """List deliveries for an event."""
        ...  # pragma: no cover
