"""Shift SQLAlchemy model."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base


class ShiftModel(Base):
    """Shift database model."""

    __tablename__ = "shifts"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    terminal_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    drawer_session_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("cash_drawer_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opening_cash: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    closing_cash: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Totals
    total_sales: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total_transactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cash_sales: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    card_sales: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    gift_card_sales: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    other_sales: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total_refunds: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    refund_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)

    # Relationships
    drawer_session: Mapped["CashDrawerSessionModel | None"] = relationship(
        "CashDrawerSessionModel", back_populates="shifts"
    )
    sales: Mapped[list["SaleModel"]] = relationship(
        "SaleModel",
        back_populates="shift",
        foreign_keys="SaleModel.shift_id",
    )
