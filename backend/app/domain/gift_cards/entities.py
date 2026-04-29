"""Gift card domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
import secrets
import string

from app.domain.common.errors import ValidationError
from app.domain.common.identifiers import new_ulid
from app.domain.common.money import Money


class GiftCardStatus(str, Enum):
    """Gift card status enumeration."""
    PENDING = "pending"          # Purchased but not yet activated
    ACTIVE = "active"            # Activated and ready to use
    REDEEMED = "redeemed"        # Fully redeemed (balance = 0)
    EXPIRED = "expired"          # Past expiry date
    CANCELLED = "cancelled"      # Manually cancelled


@dataclass(slots=True)
class GiftCard:
    """
    Gift card aggregate root.
    
    Represents a prepaid card that can be purchased, activated, and redeemed
    for purchases. Tracks balance, expiry, and redemption history.
    """
    id: str
    code: str                    # Unique redemption code (e.g., "GC-ABC123456789")
    initial_balance: Money
    current_balance: Money
    status: GiftCardStatus
    issued_date: datetime
    expiry_date: datetime | None = None
    customer_id: str | None = None    # Optional: if purchased for specific customer
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0

    @property
    def currency(self) -> str:
        """Return the currency for this gift card."""
        return self.current_balance.currency

    @staticmethod
    def generate_code() -> str:
        """
        Generate a unique gift card code.
        Format: GC-XXXXXXXXXXXX (15 characters after prefix)
        """
        chars = string.ascii_uppercase + string.digits
        code_suffix = ''.join(secrets.choice(chars) for _ in range(12))
        return f"GC-{code_suffix}"

    @staticmethod
    def purchase(
        *,
        amount: Decimal,
        currency: str = "USD",
        customer_id: str | None = None,
        validity_days: int = 365,
    ) -> GiftCard:
        """
        Create a new gift card purchase.
        
        Args:
            amount: Initial balance amount
            currency: Currency code
            customer_id: Optional customer who purchased/owns this card
            validity_days: Days until expiry (default 1 year)
        
        Returns:
            New GiftCard in PENDING status
        """
        if amount <= Decimal("0"):
            raise ValidationError("gift card amount must be positive", code="gift_card.invalid_amount")
        
        initial_balance = Money(amount, currency)
        issued_date = datetime.now(UTC)
        expiry_date = issued_date + timedelta(days=validity_days) if validity_days > 0 else None
        
        return GiftCard(
            id=new_ulid(),
            code=GiftCard.generate_code(),
            initial_balance=initial_balance,
            current_balance=initial_balance,
            status=GiftCardStatus.PENDING,
            issued_date=issued_date,
            expiry_date=expiry_date,
            customer_id=customer_id,
        )

    def activate(self) -> None:
        """
        Activate the gift card, making it ready for redemption.
        
        Raises:
            ValidationError: If card is not in PENDING status
        """
        if self.status != GiftCardStatus.PENDING:
            raise ValidationError(
                f"cannot activate gift card in {self.status} status",
                code="gift_card.invalid_status"
            )
        
        if self._is_expired():
            raise ValidationError("cannot activate expired gift card", code="gift_card.expired")
        
        self.status = GiftCardStatus.ACTIVE
        self._touch()

    def redeem(self, amount: Decimal) -> None:
        """
        Redeem a specific amount from the gift card.
        
        Args:
            amount: Amount to redeem
        
        Raises:
            ValidationError: If card is not active, expired, or has insufficient balance
        """
        if self.status != GiftCardStatus.ACTIVE:
            raise ValidationError(
                f"cannot redeem gift card in {self.status} status",
                code="gift_card.invalid_status"
            )
        
        if self._is_expired():
            self.status = GiftCardStatus.EXPIRED
            self._touch()
            raise ValidationError("gift card has expired", code="gift_card.expired")
        
        if amount <= Decimal("0"):
            raise ValidationError("redemption amount must be positive", code="gift_card.invalid_amount")
        
        redemption_money = Money(amount, self.current_balance.currency)
        
        if redemption_money.amount > self.current_balance.amount:
            raise ValidationError(
                f"insufficient balance (available: {self.current_balance.amount}, requested: {amount})",
                code="gift_card.insufficient_balance"
            )
        
        self.current_balance = self.current_balance.subtract(redemption_money)
        
        # Mark as fully redeemed if balance reaches zero
        if self.current_balance.amount == Decimal("0"):
            self.status = GiftCardStatus.REDEEMED
        
        self._touch()

    def check_balance(self) -> Money:
        """
        Get the current available balance.
        
        Returns:
            Current balance as Money object
        """
        if self._is_expired() and self.status == GiftCardStatus.ACTIVE:
            self.status = GiftCardStatus.EXPIRED
            self._touch()
        
        return self.current_balance

    def cancel(self) -> None:
        """
        Cancel the gift card, preventing any future redemptions.
        
        Raises:
            ValidationError: If card is already redeemed
        """
        if self.status == GiftCardStatus.REDEEMED:
            raise ValidationError("cannot cancel fully redeemed gift card", code="gift_card.already_redeemed")
        
        self.status = GiftCardStatus.CANCELLED
        self._touch()

    def is_usable(self) -> bool:
        """
        Check if the gift card can be used for redemption.
        
        Returns:
            True if card is active, not expired, and has balance
        """
        return (
            self.status == GiftCardStatus.ACTIVE
            and not self._is_expired()
            and self.current_balance.amount > Decimal("0")
        )

    def _is_expired(self) -> bool:
        """Check if the gift card has passed its expiry date."""
        if self.expiry_date is None:
            return False
        return datetime.now(UTC) > self.expiry_date

    def _touch(self) -> None:
        """Update version and timestamp."""
        self.version += 1
        self.updated_at = datetime.now(UTC)
