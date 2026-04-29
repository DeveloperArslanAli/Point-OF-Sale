"""
SQLAlchemy model for Promotion entity.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.session import Base


class PromotionModel(Base):
    """
    Promotion ORM model.

    Maps to app.domain.promotions.entities.Promotion
    """

    __tablename__ = "promotions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Discount rule (stored as JSON for flexibility)
    discount_rule: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Validity period
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # Usage limits
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usage_limit_per_customer: Mapped[int | None] = mapped_column(Integer)
    
    # Coupon code
    coupon_code: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    is_case_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Targeting
    customer_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    exclude_sale_items: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Combinability
    can_combine_with_other_promotions: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    # Priority
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(String(26), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    updated_by: Mapped[str] = mapped_column(String(26), nullable=False)
    
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)

    # Indexes
    __table_args__ = (
        Index("ix_promotions_status", "status"),
        Index("ix_promotions_start_date", "start_date"),
        Index("ix_promotions_end_date", "end_date"),
        Index("ix_promotions_priority", "priority"),
        CheckConstraint("usage_count >= 0", name="ck_promotions_usage_count_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"<PromotionModel(id={self.id!r}, name={self.name!r}, "
            f"status={self.status!r}, usage={self.usage_count}/{self.usage_limit})>"
        )
