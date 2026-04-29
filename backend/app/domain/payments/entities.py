"""
Payment domain entities and value objects.

Handles payment processing, methods, and transactions for the POS system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from app.domain.common.errors import ValidationError
from app.domain.common.money import Money


class PaymentMethod(str, Enum):
    """Payment method types."""

    CASH = "cash"
    CARD = "card"
    MOBILE = "mobile"
    GIFT_CARD = "gift_card"
    BANK_TRANSFER = "bank_transfer"
    CHECK = "check"


class PaymentStatus(str, Enum):
    """Payment processing status."""

    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentProvider(str, Enum):
    """Third-party payment providers."""

    INTERNAL = "internal"  # Cash, check
    STRIPE = "stripe"
    PAYPAL = "paypal"
    SQUARE = "square"


@dataclass(slots=True)
class Payment:
    """
    Payment transaction entity.

    Represents a single payment attempt for a sale.
    Supports multiple payment methods and providers.
    """

    id: str
    sale_id: str
    method: PaymentMethod
    amount: Money
    status: PaymentStatus
    provider: PaymentProvider = PaymentProvider.INTERNAL
    provider_transaction_id: Optional[str] = None
    provider_metadata: dict = field(default_factory=dict)
    
    # Card payment details (if applicable)
    card_last4: Optional[str] = None
    card_brand: Optional[str] = None
    
    # Authorization details
    authorized_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    
    # Refund tracking
    refunded_amount: Money = field(default_factory=lambda: Money(Decimal("0"), "USD"))
    refunded_at: Optional[datetime] = None
    
    # Audit fields
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""  # User ID
    notes: Optional[str] = None
    
    version: int = 1

    def __post_init__(self):
        """Validate payment on initialization."""
        if self.amount.amount <= Decimal("0"):
            raise ValidationError("Payment amount must be positive")
        
        if self.refunded_amount.amount < Decimal("0"):
            raise ValidationError("Refunded amount cannot be negative")
        
        if self.refunded_amount.amount > self.amount.amount:
            raise ValidationError("Refunded amount cannot exceed payment amount")

    @staticmethod
    def create_cash_payment(
        payment_id: str,
        sale_id: str,
        amount: Money,
        created_by: str,
    ) -> "Payment":
        """
        Create a cash payment (immediately completed).

        Args:
            payment_id: Unique payment identifier
            sale_id: Associated sale ID
            amount: Payment amount
            created_by: User creating the payment

        Returns:
            Payment instance with COMPLETED status
        """
        return Payment(
            id=payment_id,
            sale_id=sale_id,
            method=PaymentMethod.CASH,
            amount=amount,
            status=PaymentStatus.COMPLETED,
            provider=PaymentProvider.INTERNAL,
            captured_at=datetime.utcnow(),
            created_by=created_by,
        )

    @staticmethod
    def create_card_payment(
        payment_id: str,
        sale_id: str,
        amount: Money,
        provider: PaymentProvider,
        created_by: str,
    ) -> "Payment":
        """
        Create a card payment (pending authorization).

        Args:
            payment_id: Unique payment identifier
            sale_id: Associated sale ID
            amount: Payment amount
            provider: Payment provider (Stripe, PayPal, etc.)
            created_by: User creating the payment

        Returns:
            Payment instance with PENDING status
        """
        return Payment(
            id=payment_id,
            sale_id=sale_id,
            method=PaymentMethod.CARD,
            amount=amount,
            status=PaymentStatus.PENDING,
            provider=provider,
            created_by=created_by,
        )

    def authorize(
        self,
        provider_transaction_id: str,
        card_last4: Optional[str] = None,
        card_brand: Optional[str] = None,
    ) -> None:
        """
        Mark payment as authorized by provider.

        Args:
            provider_transaction_id: Provider's transaction ID
            card_last4: Last 4 digits of card (if applicable)
            card_brand: Card brand (Visa, MasterCard, etc.)
        """
        if self.status not in [PaymentStatus.PENDING]:
            raise ValidationError(f"Cannot authorize payment in {self.status} status")
        
        self.status = PaymentStatus.AUTHORIZED
        self.provider_transaction_id = provider_transaction_id
        self.card_last4 = card_last4
        self.card_brand = card_brand
        self.authorized_at = datetime.utcnow()
        self.version += 1

    def capture(self) -> None:
        """
        Capture an authorized payment.

        Moves funds from customer to merchant account.
        """
        if self.status not in [PaymentStatus.AUTHORIZED, PaymentStatus.PENDING]:
            raise ValidationError(f"Cannot capture payment in {self.status} status")
        
        self.status = PaymentStatus.CAPTURED
        self.captured_at = datetime.utcnow()
        self.version += 1

    def complete(self) -> None:
        """
        Mark payment as fully completed.

        For cash payments, this happens immediately.
        For card payments, after successful capture.
        """
        if self.status not in [PaymentStatus.CAPTURED, PaymentStatus.PENDING]:
            raise ValidationError(f"Cannot complete payment in {self.status} status")
        
        self.status = PaymentStatus.COMPLETED
        if not self.captured_at:
            self.captured_at = datetime.utcnow()
        self.version += 1

    def fail(self, reason: Optional[str] = None) -> None:
        """
        Mark payment as failed.

        Args:
            reason: Failure reason for audit trail
        """
        if self.status in [PaymentStatus.COMPLETED, PaymentStatus.REFUNDED]:
            raise ValidationError(f"Cannot fail payment in {self.status} status")
        
        self.status = PaymentStatus.FAILED
        if reason:
            self.notes = reason
        self.version += 1

    def refund(self, amount: Money, reason: Optional[str] = None) -> None:
        """
        Refund payment (full or partial).

        Args:
            amount: Amount to refund
            reason: Refund reason
        """
        if self.status not in [PaymentStatus.COMPLETED, PaymentStatus.PARTIALLY_REFUNDED]:
            raise ValidationError(f"Cannot refund payment in {self.status} status")
        
        if amount.amount <= Decimal("0"):
            raise ValidationError("Refund amount must be positive")
        
        if amount.currency != self.amount.currency:
            raise ValidationError("Refund currency must match payment currency")
        
        new_refunded = self.refunded_amount.amount + amount.amount
        if new_refunded > self.amount.amount:
            raise ValidationError("Total refunds cannot exceed payment amount")
        
        self.refunded_amount = Money(new_refunded, self.amount.currency)
        
        if new_refunded >= self.amount.amount:
            self.status = PaymentStatus.REFUNDED
        else:
            self.status = PaymentStatus.PARTIALLY_REFUNDED
        
        self.refunded_at = datetime.utcnow()
        if reason:
            self.notes = f"{self.notes or ''}\nRefund: {reason}".strip()
        self.version += 1

    def cancel(self, reason: Optional[str] = None) -> None:
        """
        Cancel a pending or authorized payment.

        Args:
            reason: Cancellation reason
        """
        if self.status not in [PaymentStatus.PENDING, PaymentStatus.AUTHORIZED]:
            raise ValidationError(f"Cannot cancel payment in {self.status} status")
        
        self.status = PaymentStatus.CANCELLED
        if reason:
            self.notes = reason
        self.version += 1

    @property
    def is_successful(self) -> bool:
        """Check if payment was successful."""
        return self.status in [
            PaymentStatus.COMPLETED,
            PaymentStatus.CAPTURED,
            PaymentStatus.PARTIALLY_REFUNDED,
        ]

    @property
    def is_pending(self) -> bool:
        """Check if payment is pending."""
        return self.status in [PaymentStatus.PENDING, PaymentStatus.AUTHORIZED]

    @property
    def remaining_amount(self) -> Money:
        """Calculate remaining (non-refunded) amount."""
        return Money(
            self.amount.amount - self.refunded_amount.amount,
            self.amount.currency,
        )
