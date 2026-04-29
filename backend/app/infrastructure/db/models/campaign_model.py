"""SQLAlchemy models for marketing campaigns and feedback."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.customers.campaigns import (
    CampaignStatus,
    CampaignTrigger,
    CampaignType,
)
from app.infrastructure.db.session import Base


class MarketingCampaignModel(Base):
    """SQLAlchemy model for marketing campaigns."""

    __tablename__ = "marketing_campaigns"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    campaign_type: Mapped[str] = mapped_column(
        Enum(CampaignType, name="campaign_type"),
        nullable=False,
        index=True,
    )
    trigger: Mapped[str] = mapped_column(
        Enum(CampaignTrigger, name="campaign_trigger"),
        nullable=False,
        default=CampaignTrigger.MANUAL,
    )
    status: Mapped[str] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"),
        nullable=False,
        default=CampaignStatus.DRAFT,
        index=True,
    )

    # Targeting (stored as JSON)
    targeting_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Content (stored as JSON)
    content_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Metrics (stored as JSON for flexibility)
    metrics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Scheduling
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Configuration
    send_rate_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurrence_pattern: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Metadata
    created_by: Mapped[str | None] = mapped_column(String(26), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)


class CampaignRecipientModel(Base):
    """SQLAlchemy model for campaign recipients."""

    __tablename__ = "campaign_recipients"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    notification_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    conversion_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)


class CustomerFeedbackModel(Base):
    """SQLAlchemy model for customer feedback."""

    __tablename__ = "customer_feedback"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    reference_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_by: Mapped[str | None] = mapped_column(String(26), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
