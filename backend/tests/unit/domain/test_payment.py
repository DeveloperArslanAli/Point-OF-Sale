"""
Unit tests for Payment entity.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from app.domain.common.errors import ValidationError
from app.domain.common.money import Money
from app.domain.payments.entities import Payment, PaymentMethod, PaymentProvider, PaymentStatus


def test_create_cash_payment():
    """Test cash payment creation."""
    payment = Payment.create_cash_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("100.00"), "USD"),
        created_by="user_123",
    )
    
    assert payment.id == "01JCTEST000000000000000001"
    assert payment.sale_id == "01JCTEST000000000000000002"
    assert payment.method == PaymentMethod.CASH
    assert payment.amount.amount == Decimal("100.00")
    assert payment.status == PaymentStatus.COMPLETED
    assert payment.provider == PaymentProvider.INTERNAL
    assert payment.is_successful is True


def test_create_card_payment():
    """Test card payment creation."""
    payment = Payment.create_card_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("150.00"), "USD"),
        provider=PaymentProvider.STRIPE,
        created_by="user_123",
    )
    
    assert payment.id == "01JCTEST000000000000000001"
    assert payment.method == PaymentMethod.CARD
    assert payment.status == PaymentStatus.PENDING
    assert payment.provider == PaymentProvider.STRIPE
    assert payment.is_pending is True


def test_authorize_payment():
    """Test payment authorization."""
    payment = Payment.create_card_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("150.00"), "USD"),
        provider=PaymentProvider.STRIPE,
        created_by="user_123",
    )
    
    payment.authorize(
        provider_transaction_id="pi_abc123",
        card_last4="4242",
        card_brand="Visa",
    )
    
    assert payment.status == PaymentStatus.AUTHORIZED
    assert payment.provider_transaction_id == "pi_abc123"
    assert payment.card_last4 == "4242"
    assert payment.card_brand == "Visa"
    assert payment.authorized_at is not None


def test_capture_payment():
    """Test payment capture."""
    payment = Payment.create_card_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("150.00"), "USD"),
        provider=PaymentProvider.STRIPE,
        created_by="user_123",
    )
    payment.authorize("pi_abc123")
    
    payment.capture()
    
    assert payment.status == PaymentStatus.CAPTURED
    assert payment.captured_at is not None


def test_complete_payment():
    """Test payment completion."""
    payment = Payment.create_card_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("150.00"), "USD"),
        provider=PaymentProvider.STRIPE,
        created_by="user_123",
    )
    payment.authorize("pi_abc123")
    payment.capture()
    
    payment.complete()
    
    assert payment.status == PaymentStatus.COMPLETED
    assert payment.is_successful is True


def test_fail_payment():
    """Test payment failure."""
    payment = Payment.create_card_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("150.00"), "USD"),
        provider=PaymentProvider.STRIPE,
        created_by="user_123",
    )
    
    payment.fail("Card declined")
    
    assert payment.status == PaymentStatus.FAILED
    assert payment.notes == "Card declined"


def test_refund_payment():
    """Test payment refund."""
    payment = Payment.create_cash_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("100.00"), "USD"),
        created_by="user_123",
    )
    
    refund_amount = Money(Decimal("30.00"), "USD")
    payment.refund(refund_amount, "Customer requested")
    
    assert payment.status == PaymentStatus.PARTIALLY_REFUNDED
    assert payment.refunded_amount.amount == Decimal("30.00")
    assert payment.remaining_amount.amount == Decimal("70.00")
    assert "Customer requested" in payment.notes


def test_full_refund():
    """Test full payment refund."""
    payment = Payment.create_cash_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("100.00"), "USD"),
        created_by="user_123",
    )
    
    payment.refund(Money(Decimal("100.00"), "USD"), "Full refund")
    
    assert payment.status == PaymentStatus.REFUNDED
    assert payment.refunded_amount.amount == Decimal("100.00")
    assert payment.remaining_amount.amount == Decimal("0.00")


def test_cancel_payment():
    """Test payment cancellation."""
    payment = Payment.create_card_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("150.00"), "USD"),
        provider=PaymentProvider.STRIPE,
        created_by="user_123",
    )
    
    payment.cancel("User cancelled")
    
    assert payment.status == PaymentStatus.CANCELLED
    assert payment.notes == "User cancelled"


def test_invalid_refund_amount():
    """Test refund with invalid amount."""
    payment = Payment.create_cash_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("100.00"), "USD"),
        created_by="user_123",
    )
    
    # Refund exceeds payment amount
    with pytest.raises(ValidationError, match="cannot exceed"):
        payment.refund(Money(Decimal("150.00"), "USD"))


def test_negative_payment_amount():
    """Test payment with negative amount."""
    with pytest.raises(ValidationError, match="negative"):
        Payment(
            id="01JCTEST000000000000000001",
            sale_id="01JCTEST000000000000000002",
            method=PaymentMethod.CASH,
            amount=Money(Decimal("-10.00"), "USD"),
            status=PaymentStatus.PENDING,
        )


def test_invalid_status_transition():
    """Test invalid payment status transition."""
    payment = Payment.create_cash_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("100.00"), "USD"),
        created_by="user_123",
    )
    
    # Cannot authorize a completed payment
    with pytest.raises(ValidationError, match="Cannot authorize"):
        payment.authorize("pi_abc123")


def test_payment_version_increment():
    """Test version increment on state changes."""
    payment = Payment.create_card_payment(
        payment_id="01JCTEST000000000000000001",
        sale_id="01JCTEST000000000000000002",
        amount=Money(Decimal("150.00"), "USD"),
        provider=PaymentProvider.STRIPE,
        created_by="user_123",
    )
    
    initial_version = payment.version
    payment.authorize("pi_abc123")
    assert payment.version == initial_version + 1
    
    payment.capture()
    assert payment.version == initial_version + 2
    
    payment.complete()
    assert payment.version == initial_version + 3
