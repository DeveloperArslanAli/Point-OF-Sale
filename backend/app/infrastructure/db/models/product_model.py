from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base
from app.infrastructure.db.utils import utcnow

if TYPE_CHECKING:
    from app.infrastructure.db.models.product_supplier_link_model import ProductSupplierLinkModel


class ProductModel(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    price_retail: Mapped[float] = mapped_column(Numeric(12,2))
    purchase_price: Mapped[float] = mapped_column(Numeric(12,2))
    category_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)

    # Relationships
    supplier_links: Mapped[List["ProductSupplierLinkModel"]] = relationship(
        "ProductSupplierLinkModel",
        back_populates="product",
        cascade="all, delete-orphan",
    )
