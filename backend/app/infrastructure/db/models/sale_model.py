from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base


class SaleModel(Base):
    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shift_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("shifts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)

    items: Mapped[list[SaleItemModel]] = relationship(
        "SaleItemModel",
        back_populates="sale",
        cascade="all, delete-orphan",
    )
    # Payment tracking from Phase 12.1 (Stripe integration)
    payments: Mapped[list["PaymentModel"]] = relationship(
        "PaymentModel",
        back_populates="sale",
        cascade="all, delete-orphan",
    )
    # Split payment allocations (Phase 12.4)
    payment_allocations: Mapped[list["SalePaymentModel"]] = relationship(
        "SalePaymentModel",
        back_populates="sale",
        cascade="all, delete-orphan",
    )
    # Shift linkage (Phase 12.6)
    shift: Mapped["ShiftModel | None"] = relationship(
        "ShiftModel",
        back_populates="sales",
        foreign_keys=[shift_id],
    )


class SaleItemModel(Base):
    __tablename__ = "sale_items"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    sale_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sale: Mapped[SaleModel] = relationship("SaleModel", back_populates="items")
