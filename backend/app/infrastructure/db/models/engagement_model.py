"""SQLAlchemy models for customer engagement tracking."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Float, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.customers.engagement import CustomerSegment, EngagementEventType
from app.infrastructure.db.session import Base


class EngagementEventModel(Base):
    """SQLAlchemy model for engagement events."""

    __tablename__ = "engagement_events"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(
        Enum(EngagementEventType, name="engagement_event_type"),
        nullable=False,
        index=True,
    )
    reference_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)


class CustomerEngagementProfileModel(Base):
    """SQLAlchemy model for customer engagement profiles."""

    __tablename__ = "customer_engagement_profiles"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(26), nullable=False, unique=True, index=True
    )
    segment: Mapped[str] = mapped_column(
        Enum(CustomerSegment, name="customer_segment"),
        nullable=False,
        default=CustomerSegment.NEW,
        index=True,
    )

    # Purchase metrics
    total_purchases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_spent: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    average_order_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    last_purchase_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Engagement metrics
    total_interactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_interaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_open_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    email_click_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Loyalty metrics
    loyalty_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    current_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifetime_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Dates
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
