"""SQLAlchemy models for webhook system."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.webhooks.entities import DeliveryStatus, WebhookEventType, WebhookStatus
from app.infrastructure.db.session import Base


class WebhookSubscriptionModel(Base):
    """SQLAlchemy model for webhook subscriptions."""

    __tablename__ = "webhook_subscriptions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret: Mapped[str] = mapped_column(String(128), nullable=False)
    events: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(WebhookStatus, name="webhook_status"),
        nullable=False,
        default=WebhookStatus.ACTIVE,
        index=True,
    )
    headers_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Retry configuration
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    retry_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    # Failure tracking
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    last_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)


class WebhookEventModel(Base):
    """SQLAlchemy model for webhook events."""

    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    event_type: Mapped[str] = mapped_column(
        Enum(WebhookEventType, name="webhook_event_type"),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)


class WebhookDeliveryModel(Base):
    """SQLAlchemy model for webhook delivery attempts."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    subscription_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(
        Enum(WebhookEventType, name="webhook_event_type", create_type=False),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(DeliveryStatus, name="delivery_status"),
        nullable=False,
        default=DeliveryStatus.PENDING,
        index=True,
    )
    request_headers_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
