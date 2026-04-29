"""
SQLAlchemy model for Payment entity.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base
from app.infrastructure.db.types import EncryptedCardLast4


class PaymentModel(Base):
    """
    Payment ORM model.

    Maps to app.domain.payments.entities.Payment
    """

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    sale_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
    )
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        CheckConstraint("amount > 0"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="internal", nullable=False)
    
    # Provider details
    provider_transaction_id: Mapped[str | None] = mapped_column(String(255))
    provider_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Card details (PCI-DSS encrypted)
    card_last4: Mapped[str | None] = mapped_column(EncryptedCardLast4())
    card_brand: Mapped[str | None] = mapped_column(String(50))
    
    # Status timestamps
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # Refund tracking
    refunded_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0"),
        nullable=False,
    )
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(String(26), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    
    version: Mapped[int] = mapped_column(default=1, nullable=False)

    # Relationships
    sale: Mapped["SaleModel"] = relationship(
        "SaleModel",
        back_populates="payments",
        lazy="joined",
    )

    # Indexes
    __table_args__ = (
        Index("ix_payments_sale_id", "sale_id"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_provider_transaction_id", "provider_transaction_id"),
        Index("ix_payments_created_at", "created_at"),
        CheckConstraint("refunded_amount >= 0", name="ck_payments_refunded_amount_positive"),
        CheckConstraint("refunded_amount <= amount", name="ck_payments_refunded_amount_lte_amount"),
    )

    def __repr__(self) -> str:
        return (
            f"<PaymentModel(id={self.id!r}, sale_id={self.sale_id!r}, "
            f"method={self.method!r}, amount={self.amount}, status={self.status!r})>"
        )
