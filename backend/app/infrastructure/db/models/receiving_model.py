"""SQLAlchemy models for purchase order receiving."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.purchase_model import PurchaseOrderModel, PurchaseOrderItemModel
    from app.infrastructure.db.models.product_model import ProductModel
    from app.infrastructure.db.models.auth.user_model import UserModel


class PurchaseOrderReceivingModel(Base):
    """Purchase order receiving record."""

    __tablename__ = "purchase_order_receivings"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    purchase_order_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )

    # Status
    status: Mapped[str] = mapped_column(
        Enum(
            "pending", "partial", "complete", "complete_with_exceptions", "cancelled",
            name="receiving_status",
            create_type=False,
        ),
        nullable=False,
        default="pending",
    )

    # Timestamps
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Receiver info
    received_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    purchase_order: Mapped["PurchaseOrderModel"] = relationship(
        "PurchaseOrderModel", back_populates="receivings"
    )
    received_by: Mapped["UserModel | None"] = relationship("UserModel")
    items: Mapped[List["ReceivingLineItemModel"]] = relationship(
        "ReceivingLineItemModel",
        back_populates="receiving",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_po_receivings_purchase_order_id", "purchase_order_id"),
        Index("ix_po_receivings_status", "status"),
        Index("ix_po_receivings_received_at", "received_at"),
    )


class ReceivingLineItemModel(Base):
    """Individual line item in a receiving record."""

    __tablename__ = "receiving_line_items"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    receiving_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("purchase_order_receivings.id", ondelete="CASCADE"), nullable=False
    )
    purchase_order_item_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("purchase_order_items.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )

    # Quantities
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_damaged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_accepted: Mapped[int] = mapped_column(Integer, nullable=False)

    # Exception tracking
    exception_type: Mapped[str | None] = mapped_column(
        Enum(
            "partial_delivery", "over_delivery", "damaged", "missing", "wrong_item", "quality_issue",
            name="receiving_exception_type",
            create_type=False,
        ),
        nullable=True,
    )
    exception_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    receiving: Mapped["PurchaseOrderReceivingModel"] = relationship(
        "PurchaseOrderReceivingModel", back_populates="items"
    )
    purchase_order_item: Mapped["PurchaseOrderItemModel"] = relationship("PurchaseOrderItemModel")
    product: Mapped["ProductModel"] = relationship("ProductModel")

    __table_args__ = (
        Index("ix_receiving_line_items_receiving_id", "receiving_id"),
        Index("ix_receiving_line_items_product_id", "product_id"),
        Index("ix_receiving_line_items_exception_type", "exception_type"),
    )
