from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base


class ReturnModel(Base):
    __tablename__ = "returns"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    sale_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    items: Mapped[list[ReturnItemModel]] = relationship(
        "ReturnItemModel",
        back_populates="return_",
        cascade="all, delete-orphan",
    )


class ReturnItemModel(Base):
    __tablename__ = "return_items"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    return_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("returns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sale_item_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("sale_items.id", ondelete="RESTRICT"),
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

    return_: Mapped[ReturnModel] = relationship("ReturnModel", back_populates="items")
