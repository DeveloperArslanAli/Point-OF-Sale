"""SQLAlchemy models for customer notifications."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.customers.notifications import (
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
)
from app.infrastructure.db.session import Base


class NotificationTemplateModel(Base):
    """SQLAlchemy model for notification templates."""

    __tablename__ = "notification_templates"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    notification_type: Mapped[str] = mapped_column(
        Enum(NotificationType, name="notification_type"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        Enum(NotificationChannel, name="notification_channel"),
        nullable=False,
    )
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)


class CustomerNotificationModel(Base):
    """SQLAlchemy model for customer notifications."""

    __tablename__ = "customer_notifications"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(
        Enum(NotificationType, name="notification_type", create_type=False),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        Enum(NotificationChannel, name="notification_channel", create_type=False),
        nullable=False,
    )
    priority: Mapped[str] = mapped_column(
        Enum(NotificationPriority, name="notification_priority"),
        nullable=False,
        default=NotificationPriority.NORMAL,
    )
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(NotificationStatus, name="notification_status"),
        nullable=False,
        default=NotificationStatus.PENDING,
        index=True,
    )
    reference_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)


class CustomerNotificationPreferencesModel(Base):
    """SQLAlchemy model for customer notification preferences."""

    __tablename__ = "customer_notification_preferences"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(26), nullable=False, unique=True, index=True
    )

    # Channel preferences
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Category preferences
    transactional_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    loyalty_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    marketing_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    engagement_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Quiet hours
    quiet_hours_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quiet_hours_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
