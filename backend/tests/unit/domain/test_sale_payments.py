"""Unit tests for split payment functionality in Sale entity."""
import pytest
from datetime import datetime, UTC
from decimal import Decimal

from app.domain.common.errors import ValidationError
from app.domain.common.money import Money
from app.domain.sales.entities import Sale, SalePayment


class TestSalePayment:
    """Test cases for SalePayment entity."""

    def test_create_valid_payment(self):
        """Test creating a valid payment."""
        payment = SalePayment.create(
            payment_method="cash",
            amount=Decimal("50.00"),
            currency="USD",
            reference_number="REF123",
            card_last_four="1234",
        )
        
        assert payment.payment_method == "cash"
        assert payment.amount.amount == Decimal("50.00")
        assert payment.amount.currency == "USD"
        assert payment.reference_number == "REF123"
        assert payment.card_last_four == "1234"
        assert isinstance(payment.created_at, datetime)

    def test_create_payment_without_optionals(self):
        """Test creating payment without optional fields."""
        payment = SalePayment.create(
            payment_method="card",
            amount=Decimal("100.00"),
            currency="USD",
        )
        
        assert payment.payment_method == "card"
        assert payment.amount.amount == Decimal("100.00")
        assert payment.reference_number is None
        assert payment.card_last_four is None

    def test_create_payment_requires_method(self):
        """Test that payment_method is required."""
        with pytest.raises(ValidationError, match="payment_method is required"):
            SalePayment.create(
                payment_method="",
                amount=Decimal("50.00"),
                currency="USD",
            )

    def test_create_payment_requires_positive_amount(self):
        """Test that amount must be positive."""
        with pytest.raises(ValidationError, match="payment amount must be positive"):
            SalePayment.create(
                payment_method="cash",
                amount=Decimal("0"),
                currency="USD",
            )


class TestSaleWithSplitPayments:
    """Test cases for Sale entity with multiple payments."""

    def test_add_single_payment(self):
        """Test adding a single payment to a sale."""
        sale = Sale.start("USD")
        sale.add_line(product_id="product-1", quantity=2, unit_price=Decimal("10.00"))
        
        payment = SalePayment.create(
            payment_method="cash",
            amount=Decimal("20.00"),
            currency="USD",
        )
        sale.add_payment(payment)
        
        assert len(sale.payments) == 1
        assert sale.payments[0].payment_method == "cash"
        assert sale.total_paid.amount == Decimal("20.00")

    def test_add_multiple_payments(self):
        """Test adding multiple payments (split payment)."""
        sale = Sale.start("USD")
        sale.add_line(product_id="product-1", quantity=1, unit_price=Decimal("100.00"))
        
        # Pay with cash + card
        cash_payment = SalePayment.create(
            payment_method="cash",
            amount=Decimal("60.00"),
            currency="USD",
        )
        card_payment = SalePayment.create(
            payment_method="card",
            amount=Decimal("40.00"),
            currency="USD",
            card_last_four="5678",
        )
        
        sale.add_payment(cash_payment)
        sale.add_payment(card_payment)
        
        assert len(sale.payments) == 2
        assert sale.total_paid.amount == Decimal("100.00")

    def test_add_payment_validates_currency(self):
        """Test that payment currency must match sale currency."""
        sale = Sale.start("USD")
        sale.add_line(product_id="product-1", quantity=1, unit_price=Decimal("50.00"))
        
        eur_payment = SalePayment.create(
            payment_method="cash",
            amount=Decimal("50.00"),
            currency="EUR",
        )
        
        with pytest.raises(ValidationError, match="payment currency mismatch"):
            sale.add_payment(eur_payment)

    def test_validate_payments_exact_match(self):
        """Test validating payments that exactly match sale total."""
        sale = Sale.start("USD")
        sale.add_line(product_id="product-1", quantity=3, unit_price=Decimal("25.00"))
        
        payment = SalePayment.create(
            payment_method="card",
            amount=Decimal("75.00"),
            currency="USD",
        )
        sale.add_payment(payment)
        
        # Should not raise
        sale.validate_payments()

    def test_validate_payments_underpayment(self):
        """Test validation fails when payments don't cover total."""
        sale = Sale.start("USD")
        sale.add_line(product_id="product-1", quantity=2, unit_price=Decimal("30.00"))
        
        payment = SalePayment.create(
            payment_method="cash",
            amount=Decimal("50.00"),
            currency="USD",
        )
        sale.add_payment(payment)
        
        with pytest.raises(ValidationError, match="payment total.*does not match sale total"):
            sale.validate_payments()

    def test_validate_payments_overpayment(self):
        """Test validation fails when payments exceed total."""
        sale = Sale.start("USD")
        sale.add_line(product_id="product-1", quantity=1, unit_price=Decimal("20.00"))
        
        payment = SalePayment.create(
            payment_method="cash",
            amount=Decimal("30.00"),
            currency="USD",
        )
        sale.add_payment(payment)
        
        with pytest.raises(ValidationError, match="payment total.*does not match sale total"):
            sale.validate_payments()

    def test_validate_payments_split_exact(self):
        """Test validation passes with exact split payment."""
        sale = Sale.start("USD")
        sale.add_line(product_id="product-1", quantity=4, unit_price=Decimal("12.50"))
        
        # Total: $50.00
        cash = SalePayment.create(
            payment_method="cash",
            amount=Decimal("30.00"),
            currency="USD",
        )
        card = SalePayment.create(
            payment_method="card",
            amount=Decimal("20.00"),
            currency="USD",
        )
        
        sale.add_payment(cash)
        sale.add_payment(card)
        
        # Should not raise
        sale.validate_payments()

    def test_validate_payments_no_payments(self):
        """Test validation fails when no payments added."""
        sale = Sale.start("USD")
        sale.add_line(product_id="product-1", quantity=1, unit_price=Decimal("15.00"))
        
        with pytest.raises(ValidationError, match="sale must have at least one payment"):
            sale.validate_payments()

    def test_total_paid_empty_payments(self):
        """Test total_paid returns zero when no payments."""
        sale = Sale.start("USD")
        assert sale.total_paid.amount == Decimal("0")
        assert sale.total_paid.currency == "USD"

    def test_close_sale_validates_payments(self):
        """Test that closing a sale validates payments."""
        sale = Sale.start("USD")
        sale.add_line(product_id="product-1", quantity=2, unit_price=Decimal("15.00"))
        
        # Add insufficient payment
        payment = SalePayment.create(
            payment_method="cash",
            amount=Decimal("20.00"),
            currency="USD",
        )
        sale.add_payment(payment)
        
        # Closing should fail due to payment validation
        with pytest.raises(ValidationError, match="payment total.*does not match sale total"):
            sale.close()

    def test_close_sale_with_valid_payments(self):
        """Test closing sale with valid payments succeeds."""
        sale = Sale.start("USD")
        sale.add_line(product_id="product-1", quantity=1, unit_price=Decimal("45.00"))
        
        payment = SalePayment.create(
            payment_method="card",
            amount=Decimal("45.00"),
            currency="USD",
        )
        sale.add_payment(payment)
        
        sale.close()
        assert sale.closed_at is not None


