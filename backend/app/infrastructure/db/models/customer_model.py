from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base
from app.infrastructure.db.types import EncryptedEmail, EncryptedPhone

if TYPE_CHECKING:
    from app.infrastructure.db.models.gift_card_model import GiftCardModel
    from app.infrastructure.db.models.loyalty_model import LoyaltyAccountModel


class CustomerModel(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    
    # PII fields with encryption (GDPR compliant)
    email: Mapped[str] = mapped_column(EncryptedEmail(), nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=True, unique=True, index=True)  # For lookups
    phone: Mapped[str | None] = mapped_column(EncryptedPhone(), nullable=True)
    
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    
    # GDPR Consent Management
    consent_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    consent_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Right to Erasure (GDPR Article 17)
    erasure_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    erasure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    gift_cards: Mapped[list["GiftCardModel"]] = relationship(
        "GiftCardModel",
        back_populates="customer",
        cascade="all, delete-orphan"
    )
    loyalty_account: Mapped["LoyaltyAccountModel | None"] = relationship(
        "LoyaltyAccountModel",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan",
    )
