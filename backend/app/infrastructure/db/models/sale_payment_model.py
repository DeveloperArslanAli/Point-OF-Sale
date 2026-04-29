"""SalePayment SQLAlchemy model."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base


class SalePaymentModel(Base):
    """Sale payment database model (for split payments)."""

    __tablename__ = "sale_payments"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    sale_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    card_last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    gift_card_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("gift_cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    gift_card_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationship back to sale
    sale: Mapped["SaleModel"] = relationship("SaleModel", back_populates="payment_allocations")
