"""SQLAlchemy model for supplier ranking weights."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Integer, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.session import Base
from app.infrastructure.db.utils import utcnow


class SupplierRankingWeightsModel(Base):
    """Database model for tenant-specific supplier ranking weight configuration."""
    
    __tablename__ = "supplier_ranking_weights"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(26), unique=True, nullable=False, index=True)
    
    # Ranking weights (sum to 1.0)
    price_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.30")
    )
    lead_time_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.20")
    )
    quality_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.20")
    )
    reliability_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.15")
    )
    fill_rate_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.15")
    )
    
    # Minimum thresholds
    min_quality_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.0")
    )
    min_reliability_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.0")
    )
    max_lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Preferred supplier bonus
    preferred_supplier_bonus: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.10")
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
