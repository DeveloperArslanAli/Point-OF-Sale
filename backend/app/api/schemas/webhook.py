"""Pydantic schemas for webhook API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class WebhookSubscriptionCreate(BaseModel):
    """Request to create a webhook subscription."""

    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    events: list[str] = Field(min_length=1, description="List of event types to subscribe to")
    headers: dict[str, str] | None = Field(default=None, description="Custom headers")
    description: str = Field(default="", max_length=1000)
    max_retries: int = Field(default=5, ge=0, le=10)
    retry_interval_seconds: int = Field(default=60, ge=10, le=3600)


class WebhookSubscriptionUpdate(BaseModel):
    """Request to update a webhook subscription."""

    expected_version: int = Field(ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    url: HttpUrl | None = None
    events: list[str] | None = Field(default=None, min_length=1)
    headers: dict[str, str] | None = None
    description: str | None = Field(default=None, max_length=1000)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    retry_interval_seconds: int | None = Field(default=None, ge=10, le=3600)


class WebhookSubscriptionOut(BaseModel):
    """Webhook subscription output."""

    id: str
    name: str
    url: str
    events: list[str]
    status: str
    headers: dict[str, str]
    description: str
    max_retries: int
    retry_interval_seconds: int
    consecutive_failures: int
    last_failure_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class WebhookSubscriptionWithSecretOut(WebhookSubscriptionOut):
    """Webhook subscription output with secret (for creation/regeneration)."""

    secret: str


class WebhookSubscriptionListOut(BaseModel):
    """Paginated list of webhook subscriptions."""

    items: list[WebhookSubscriptionOut]
    total: int
    page: int
    limit: int


class WebhookEventOut(BaseModel):
    """Webhook event output."""

    id: str
    event_type: str
    payload: dict
    reference_id: str | None
    created_at: datetime


class WebhookEventListOut(BaseModel):
    """Paginated list of webhook events."""

    items: list[WebhookEventOut]
    total: int
    page: int
    limit: int


class WebhookDeliveryOut(BaseModel):
    """Webhook delivery output."""

    id: str
    subscription_id: str
    event_id: str
    event_type: str
    url: str
    status: str
    response_status_code: int | None
    error_message: str | None
    attempt_number: int
    max_attempts: int
    next_retry_at: datetime | None
    created_at: datetime
    delivered_at: datetime | None
    duration_ms: int | None


class WebhookDeliveryListOut(BaseModel):
    """Paginated list of webhook deliveries."""

    items: list[WebhookDeliveryOut]
    total: int
    page: int
    limit: int


class WebhookTestRequest(BaseModel):
    """Request to send a test webhook."""

    event_type: str = Field(description="Event type to test")
    payload: dict = Field(default_factory=dict, description="Test payload")


class WebhookTestResult(BaseModel):
    """Result of a test webhook."""

    success: bool
    status_code: int | None
    response_body: str | None
    error_message: str | None
    duration_ms: int


class WebhookEventTypes(BaseModel):
    """List of available webhook event types."""

    event_types: list[dict[str, str]]
