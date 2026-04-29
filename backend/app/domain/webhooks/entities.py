"""Webhook system domain entities."""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.domain.common.errors import ValidationError
from app.domain.common.identifiers import new_ulid


class WebhookEventType(str, Enum):
    """Types of events that can trigger webhooks."""

    # Sale events
    SALE_CREATED = "sale.created"
    SALE_COMPLETED = "sale.completed"
    SALE_VOIDED = "sale.voided"

    # Inventory events
    INVENTORY_LOW = "inventory.low"
    INVENTORY_UPDATED = "inventory.updated"
    INVENTORY_RECEIVED = "inventory.received"

    # Customer events
    CUSTOMER_CREATED = "customer.created"
    CUSTOMER_UPDATED = "customer.updated"
    CUSTOMER_DEACTIVATED = "customer.deactivated"

    # Order events
    ORDER_CREATED = "order.created"
    ORDER_SHIPPED = "order.shipped"
    ORDER_DELIVERED = "order.delivered"

    # Product events
    PRODUCT_CREATED = "product.created"
    PRODUCT_UPDATED = "product.updated"
    PRODUCT_DELETED = "product.deleted"

    # Return events
    RETURN_CREATED = "return.created"
    RETURN_APPROVED = "return.approved"
    RETURN_COMPLETED = "return.completed"

    # Employee events
    EMPLOYEE_CLOCK_IN = "employee.clock_in"
    EMPLOYEE_CLOCK_OUT = "employee.clock_out"

    # Loyalty events
    LOYALTY_POINTS_EARNED = "loyalty.points_earned"
    LOYALTY_TIER_CHANGED = "loyalty.tier_changed"

    # Gift card events
    GIFT_CARD_CREATED = "gift_card.created"
    GIFT_CARD_REDEEMED = "gift_card.redeemed"


class WebhookStatus(str, Enum):
    """Status of a webhook subscription."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"  # Suspended due to failures


class DeliveryStatus(str, Enum):
    """Status of a webhook delivery attempt."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass(slots=True)
class WebhookSubscription:
    """A webhook subscription configuration."""

    id: str
    name: str
    url: str
    secret: str
    events: list[WebhookEventType]
    status: WebhookStatus = WebhookStatus.ACTIVE
    headers: dict[str, str] = field(default_factory=dict)
    description: str = ""

    # Retry configuration
    max_retries: int = 5
    retry_interval_seconds: int = 60

    # Failure tracking
    consecutive_failures: int = 0
    failure_threshold: int = 10  # Suspend after this many consecutive failures
    last_failure_at: datetime | None = None

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0

    @staticmethod
    def create(
        *,
        name: str,
        url: str,
        events: list[WebhookEventType],
        secret: str | None = None,
        headers: dict[str, str] | None = None,
        description: str = "",
        max_retries: int = 5,
        retry_interval_seconds: int = 60,
    ) -> WebhookSubscription:
        """Create a new webhook subscription."""
        if not name or not name.strip():
            raise ValidationError(
                "Webhook name is required", code="webhook.invalid_name"
            )
        if not url or not url.strip():
            raise ValidationError(
                "Webhook URL is required", code="webhook.invalid_url"
            )
        if not url.startswith(("http://", "https://")):
            raise ValidationError(
                "Webhook URL must be HTTP or HTTPS",
                code="webhook.invalid_url_scheme",
            )
        if not events:
            raise ValidationError(
                "At least one event type is required",
                code="webhook.no_events",
            )

        # Generate secret if not provided
        if not secret:
            import secrets

            secret = secrets.token_urlsafe(32)

        return WebhookSubscription(
            id=new_ulid(),
            name=name.strip(),
            url=url.strip(),
            secret=secret,
            events=events,
            headers=headers or {},
            description=description.strip(),
            max_retries=max_retries,
            retry_interval_seconds=retry_interval_seconds,
        )

    def is_subscribed_to(self, event_type: WebhookEventType) -> bool:
        """Check if this webhook is subscribed to an event type."""
        return event_type in self.events

    def add_event(self, event_type: WebhookEventType) -> bool:
        """Add an event type subscription."""
        if event_type not in self.events:
            self.events.append(event_type)
            self._touch()
            return True
        return False

    def remove_event(self, event_type: WebhookEventType) -> bool:
        """Remove an event type subscription."""
        if event_type in self.events:
            self.events.remove(event_type)
            self._touch()
            return True
        return False

    def activate(self) -> None:
        """Activate the webhook subscription."""
        if self.status != WebhookStatus.ACTIVE:
            self.status = WebhookStatus.ACTIVE
            self.consecutive_failures = 0
            self._touch()

    def deactivate(self) -> None:
        """Deactivate the webhook subscription."""
        if self.status != WebhookStatus.INACTIVE:
            self.status = WebhookStatus.INACTIVE
            self._touch()

    def record_success(self) -> None:
        """Record a successful delivery."""
        self.consecutive_failures = 0
        if self.status == WebhookStatus.SUSPENDED:
            self.status = WebhookStatus.ACTIVE
        self._touch()

    def record_failure(self) -> None:
        """Record a failed delivery."""
        self.consecutive_failures += 1
        self.last_failure_at = datetime.now(UTC)
        if self.consecutive_failures >= self.failure_threshold:
            self.status = WebhookStatus.SUSPENDED
        self._touch()

    def generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for payload verification."""
        return hmac.new(
            self.secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _touch(self) -> None:
        """Update timestamp and version."""
        self.updated_at = datetime.now(UTC)
        self.version += 1


@dataclass(slots=True)
class WebhookEvent:
    """A webhook event to be delivered."""

    id: str
    event_type: WebhookEventType
    payload: dict[str, Any]
    reference_id: str | None = None  # ID of the related entity
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def create(
        *,
        event_type: WebhookEventType,
        payload: dict[str, Any],
        reference_id: str | None = None,
    ) -> WebhookEvent:
        """Create a new webhook event."""
        return WebhookEvent(
            id=new_ulid(),
            event_type=event_type,
            payload=payload,
            reference_id=reference_id,
        )

    def to_json(self) -> str:
        """Serialize event to JSON."""
        return json.dumps(
            {
                "id": self.id,
                "type": self.event_type.value,
                "payload": self.payload,
                "reference_id": self.reference_id,
                "created_at": self.created_at.isoformat(),
            },
            default=str,
        )


@dataclass(slots=True)
class WebhookDelivery:
    """Record of a webhook delivery attempt."""

    id: str
    subscription_id: str
    event_id: str
    event_type: WebhookEventType
    url: str
    status: DeliveryStatus = DeliveryStatus.PENDING
    request_headers: dict[str, str] = field(default_factory=dict)
    request_body: str = ""
    response_status_code: int | None = None
    response_body: str | None = None
    error_message: str | None = None
    attempt_number: int = 1
    max_attempts: int = 5
    next_retry_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    delivered_at: datetime | None = None
    duration_ms: int | None = None

    @staticmethod
    def create(
        *,
        subscription: WebhookSubscription,
        event: WebhookEvent,
    ) -> WebhookDelivery:
        """Create a new delivery record."""
        payload = event.to_json()
        signature = subscription.generate_signature(payload)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Id": event.id,
            "X-Webhook-Event": event.event_type.value,
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Timestamp": str(int(event.created_at.timestamp())),
            **subscription.headers,
        }

        return WebhookDelivery(
            id=new_ulid(),
            subscription_id=subscription.id,
            event_id=event.id,
            event_type=event.event_type,
            url=subscription.url,
            request_headers=headers,
            request_body=payload,
            max_attempts=subscription.max_retries,
        )

    def mark_success(
        self,
        *,
        status_code: int,
        response_body: str | None = None,
        duration_ms: int,
    ) -> None:
        """Mark delivery as successful."""
        self.status = DeliveryStatus.SUCCESS
        self.response_status_code = status_code
        self.response_body = response_body
        self.delivered_at = datetime.now(UTC)
        self.duration_ms = duration_ms

    def mark_failed(
        self,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
        error_message: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Mark delivery as failed."""
        self.response_status_code = status_code
        self.response_body = response_body
        self.error_message = error_message
        self.duration_ms = duration_ms

        if self.attempt_number < self.max_attempts:
            self.status = DeliveryStatus.RETRYING
            # Exponential backoff: 1min, 2min, 4min, 8min, 16min
            retry_delay = 60 * (2 ** (self.attempt_number - 1))
            self.next_retry_at = datetime.now(UTC) + __import__("datetime").timedelta(
                seconds=retry_delay
            )
        else:
            self.status = DeliveryStatus.FAILED

    def can_retry(self) -> bool:
        """Check if delivery can be retried."""
        return (
            self.status == DeliveryStatus.RETRYING
            and self.attempt_number < self.max_attempts
        )

    def increment_attempt(self) -> None:
        """Increment attempt counter for retry."""
        self.attempt_number += 1
        self.next_retry_at = None
