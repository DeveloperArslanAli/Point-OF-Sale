"""Unit tests for gift card domain entities."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.common.errors import ValidationError
from app.domain.common.money import Money
from app.domain.gift_cards.entities import GiftCard, GiftCardStatus


class TestGiftCardPurchase:
    """Test gift card purchase."""

    def test_purchase_creates_pending_card(self) -> None:
        """Test that purchasing creates a card in PENDING status."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        
        assert gift_card.status == GiftCardStatus.PENDING
        assert gift_card.initial_balance == Money(Decimal("50.00"), currency="USD")
        assert gift_card.current_balance == Money(Decimal("50.00"), currency="USD")
        assert gift_card.code.startswith("GC-")
        assert len(gift_card.code) == 15  # GC- + 12 chars
        assert gift_card.expiry_date is not None

    def test_purchase_with_customer(self) -> None:
        """Test purchasing with a customer ID."""
        customer_id = "01HXTEST123456789"
        
        gift_card = GiftCard.purchase(amount=Decimal("100.00"), currency="USD", customer_id=customer_id)
        
        assert gift_card.customer_id == customer_id

    def test_purchase_with_validity_days(self) -> None:
        """Test purchasing with custom validity period."""
        validity_days = 180
        
        gift_card = GiftCard.purchase(amount=Decimal("75.00"), currency="USD", validity_days=validity_days)
        
        # Check expiry is approximately 180 days from now
        assert gift_card.expiry_date is not None
        expected_expiry = datetime.now(timezone.utc) + timedelta(days=validity_days)
        delta = abs((gift_card.expiry_date - expected_expiry).total_seconds())
        assert delta < 5  # Within 5 seconds

    def test_purchase_rejects_negative_amount(self) -> None:
        """Test that purchasing with negative amount fails."""
        with pytest.raises(ValidationError, match="gift card amount must be positive"):
            GiftCard.purchase(amount=Decimal("-10.00"), currency="USD")

    def test_purchase_rejects_zero_amount(self) -> None:
        """Test that purchasing with zero amount fails."""
        with pytest.raises(ValidationError, match="gift card amount must be positive"):
            GiftCard.purchase(amount=Decimal("0.00"), currency="USD")


class TestGiftCardActivation:
    """Test gift card activation."""

    def test_activate_transitions_pending_to_active(self) -> None:
        """Test activating a PENDING card transitions to ACTIVE."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        
        gift_card.activate()
        
        assert gift_card.status == GiftCardStatus.ACTIVE

    def test_activate_rejects_already_active(self) -> None:
        """Test that activating an already ACTIVE card fails."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        gift_card.activate()
        
        with pytest.raises(ValidationError, match="cannot activate gift card"):
            gift_card.activate()

    def test_activate_expired_card_fails(self) -> None:
        """Test that activating an expired card fails."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD", validity_days=0)
        
        # Force expiry
        gift_card.expiry_date = datetime.now(timezone.utc) - timedelta(days=1)
        
        with pytest.raises(ValidationError, match="cannot activate expired gift card"):
            gift_card.activate()

    def test_activate_increments_version(self) -> None:
        """Test that activation increments version."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        original_version = gift_card.version
        
        gift_card.activate()
        
        assert gift_card.version == original_version + 1


class TestGiftCardRedemption:
    """Test gift card redemption."""

    def test_redeem_deducts_from_balance(self) -> None:
        """Test that redeeming deducts from current balance."""
        gift_card = GiftCard.purchase(amount=Decimal("100.00"), currency="USD")
        gift_card.activate()
        
        gift_card.redeem(Decimal("30.00"))
        
        expected_balance = Money(Decimal("70.00"), currency="USD")
        assert gift_card.current_balance == expected_balance
        assert gift_card.status == GiftCardStatus.ACTIVE

    def test_redeem_full_balance_transitions_to_redeemed(self) -> None:
        """Test that redeeming full balance transitions to REDEEMED."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        gift_card.activate()
        
        gift_card.redeem(Decimal("50.00"))
        
        assert gift_card.current_balance == Money(Decimal("0.00"), currency="USD")
        assert gift_card.status == GiftCardStatus.REDEEMED

    def test_redeem_rejects_insufficient_balance(self) -> None:
        """Test that redeeming more than balance fails."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        gift_card.activate()
        
        with pytest.raises(ValidationError, match="insufficient balance"):
            gift_card.redeem(Decimal("75.00"))

    def test_redeem_rejects_pending_card(self) -> None:
        """Test that redeeming a PENDING card fails."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        
        with pytest.raises(ValidationError, match="cannot redeem gift card"):
            gift_card.redeem(Decimal("10.00"))

    def test_redeem_rejects_expired_card(self) -> None:
        """Test that redeeming an expired card fails."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        gift_card.activate()
        
        # Force expiry
        gift_card.expiry_date = datetime.now(timezone.utc) - timedelta(days=1)
        
        with pytest.raises(ValidationError, match="gift card has expired"):
            gift_card.redeem(Decimal("10.00"))

    def test_redeem_increments_version(self) -> None:
        """Test that redemption increments version."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        gift_card.activate()
        original_version = gift_card.version
        
        gift_card.redeem(Decimal("10.00"))
        
        assert gift_card.version == original_version + 1


class TestGiftCardBalanceCheck:
    """Test gift card balance checking."""

    def test_check_balance_returns_current_balance(self) -> None:
        """Test that checking balance returns current balance."""
        gift_card = GiftCard.purchase(amount=Decimal("100.00"), currency="USD")
        gift_card.activate()
        
        balance = gift_card.check_balance()
        
        assert balance == Money(Decimal("100.00"), currency="USD")

    def test_check_balance_auto_expires_expired_card(self) -> None:
        """Test that checking balance auto-expires an expired card."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        gift_card.activate()
        
        # Force expiry
        gift_card.expiry_date = datetime.now(timezone.utc) - timedelta(days=1)
        
        balance = gift_card.check_balance()
        
        # Balance remains but status transitions to EXPIRED
        assert balance == Money(Decimal("50.00"), currency="USD")
        assert gift_card.status == GiftCardStatus.EXPIRED

    def test_is_usable_true_for_active_card(self) -> None:
        """Test that is_usable returns True for valid active card."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        gift_card.activate()
        
        assert gift_card.is_usable() is True

    def test_is_usable_false_for_pending_card(self) -> None:
        """Test that is_usable returns False for pending card."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        
        assert gift_card.is_usable() is False

    def test_is_usable_false_for_expired_card(self) -> None:
        """Test that is_usable returns False for expired card."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD", validity_days=0)
        gift_card.activate()
        
        # Force expiry
        gift_card.expiry_date = datetime.now(timezone.utc) - timedelta(days=1)
        
        assert gift_card.is_usable() is False

    def test_is_usable_false_for_zero_balance(self) -> None:
        """Test that is_usable returns False for card with zero balance."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        gift_card.activate()
        gift_card.redeem(Decimal("50.00"))
        
        assert gift_card.is_usable() is False
        assert gift_card.status == GiftCardStatus.REDEEMED


class TestGiftCardCancellation:
    """Test gift card cancellation."""

    def test_cancel_transitions_to_cancelled(self) -> None:
        """Test that cancelling transitions to CANCELLED."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        
        gift_card.cancel()
        
        assert gift_card.status == GiftCardStatus.CANCELLED

    def test_cancel_active_card(self) -> None:
        """Test that cancelling an active card works."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        gift_card.activate()
        
        gift_card.cancel()
        
        assert gift_card.status == GiftCardStatus.CANCELLED

    def test_cancel_rejects_redeemed_card(self) -> None:
        """Test that cancelling a fully redeemed card fails."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        gift_card.activate()
        gift_card.redeem(Decimal("50.00"))
        
        with pytest.raises(ValidationError, match="cannot cancel"):
            gift_card.cancel()

    def test_cancel_increments_version(self) -> None:
        """Test that cancellation increments version."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        original_version = gift_card.version
        
        gift_card.cancel()
        
        assert gift_card.version == original_version + 1


class TestGiftCardCodeGeneration:
    """Test gift card code generation."""

    def test_code_format(self) -> None:
        """Test that generated codes have correct format."""
        gift_card = GiftCard.purchase(amount=Decimal("50.00"), currency="USD")
        
        assert gift_card.code.startswith("GC-")
        assert len(gift_card.code) == 15
        # Check remaining 12 chars are alphanumeric uppercase
        code_suffix = gift_card.code[3:]
        assert code_suffix.isalnum()
        assert code_suffix.isupper()

    def test_codes_are_unique(self) -> None:
        """Test that generated codes are unique."""
        codes = {GiftCard.purchase(amount=Decimal("50.00"), currency="USD").code for _ in range(100)}
        
        # All 100 codes should be unique
        assert len(codes) == 100
