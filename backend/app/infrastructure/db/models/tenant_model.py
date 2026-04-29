from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.session import Base
from app.infrastructure.db.utils import utcnow

class TenantModel(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=True)  # For custom domains
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    subscription_plan_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("subscription_plans.id"), nullable=True)
    
    # Subscription status
    subscription_status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    billing_cycle: Mapped[str | None] = mapped_column(String(20), default="monthly", nullable=True)
    
    # Billing integration
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    
    # Trial management
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
