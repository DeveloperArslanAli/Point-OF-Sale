from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base
# Runtime import to ensure relationship target is registered when mappers are configured
from app.infrastructure.db.models.receiving_model import PurchaseOrderReceivingModel  # noqa: F401

if TYPE_CHECKING:
    from app.infrastructure.db.models.receiving_model import PurchaseOrderReceivingModel


class PurchaseOrderModel(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)

    items: Mapped[list[PurchaseOrderItemModel]] = relationship(
        "PurchaseOrderItemModel",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )
    
    receivings: Mapped[List["PurchaseOrderReceivingModel"]] = relationship(
        "PurchaseOrderReceivingModel",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )


class PurchaseOrderItemModel(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    purchase_order_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    purchase_order: Mapped[PurchaseOrderModel] = relationship("PurchaseOrderModel", back_populates="items")
