"""SQLAlchemy model for product-supplier links."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.product_model import ProductModel
    from app.infrastructure.db.models.supplier_model import SupplierModel


class ProductSupplierLinkModel(Base):
    """Product-Supplier link with cost/lead time overrides."""

    __tablename__ = "product_supplier_links"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    product_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )

    # Cost information
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    minimum_order_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Lead time
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)

    # Supplier ranking
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    product: Mapped["ProductModel"] = relationship("ProductModel", back_populates="supplier_links")
    supplier: Mapped["SupplierModel"] = relationship("SupplierModel", back_populates="product_links")

    __table_args__ = (
        UniqueConstraint("product_id", "supplier_id", name="uq_product_supplier_link"),
        Index("ix_product_supplier_links_product_id", "product_id"),
        Index("ix_product_supplier_links_supplier_id", "supplier_id"),
        Index("ix_product_supplier_links_is_preferred", "is_preferred"),
        Index("ix_product_supplier_links_priority", "priority"),
    )
