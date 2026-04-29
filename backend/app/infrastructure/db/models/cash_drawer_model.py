"""Cash drawer SQLAlchemy models."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base


class CashDrawerSessionModel(Base):
    """Cash drawer session database model."""

    __tablename__ = "cash_drawer_sessions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    terminal_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    opened_by: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    closed_by: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    opening_float: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    closing_count: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    expected_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    over_short: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)

    # Relationships
    movements: Mapped[list["CashMovementModel"]] = relationship(
        "CashMovementModel",
        back_populates="drawer_session",
        cascade="all, delete-orphan",
        order_by="CashMovementModel.created_at",
    )
    shifts: Mapped[list["ShiftModel"]] = relationship(
        "ShiftModel",
        back_populates="drawer_session",
    )


class CashMovementModel(Base):
    """Cash movement database model."""

    __tablename__ = "cash_movements"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    drawer_session_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("cash_drawer_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationship
    drawer_session: Mapped[CashDrawerSessionModel] = relationship(
        "CashDrawerSessionModel", back_populates="movements"
    )
