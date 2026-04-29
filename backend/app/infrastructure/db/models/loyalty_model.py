"""SQLAlchemy models for customer loyalty program."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.customers.loyalty import LoyaltyTier, PointTransactionType
from app.infrastructure.db.session import Base


class LoyaltyAccountModel(Base):
    """SQLAlchemy model for loyalty accounts."""

    __tablename__ = "loyalty_accounts"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    current_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifetime_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tier: Mapped[str] = mapped_column(
        Enum(LoyaltyTier, name="loyalty_tier"),
        nullable=False,
        default=LoyaltyTier.BRONZE,
    )
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)

    # Relationships
    customer: Mapped["CustomerModel"] = relationship(
        "CustomerModel",
        back_populates="loyalty_account",
    )
    transactions: Mapped[list["LoyaltyPointTransactionModel"]] = relationship(
        "LoyaltyPointTransactionModel",
        back_populates="loyalty_account",
        cascade="all, delete-orphan",
        order_by="desc(LoyaltyPointTransactionModel.created_at)",
    )


class LoyaltyPointTransactionModel(Base):
    """SQLAlchemy model for loyalty point transactions."""

    __tablename__ = "loyalty_point_transactions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    loyalty_account_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("loyalty_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transaction_type: Mapped[str] = mapped_column(
        Enum(PointTransactionType, name="point_transaction_type"),
        nullable=False,
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)

    # Relationships
    loyalty_account: Mapped["LoyaltyAccountModel"] = relationship(
        "LoyaltyAccountModel",
        back_populates="transactions",
    )


# Import CustomerModel for relationship type hints
from app.infrastructure.db.models.customer_model import CustomerModel  # noqa: E402
