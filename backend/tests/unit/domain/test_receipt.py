"""Unit tests for Receipt domain entities."""

import pytest
from datetime import datetime
from decimal import Decimal

from app.domain.common.money import Money
from app.domain.receipts import Receipt, ReceiptLineItem, ReceiptPayment, ReceiptTotals


def test_create_receipt_line_item():
    """Test creating a receipt line item."""
    item = ReceiptLineItem(
        product_name="Test Product",
        sku="SKU123",
        quantity=Decimal("2"),
        unit_price=Money(Decimal("10.00"), "USD"),
        line_total=Money(Decimal("20.00"), "USD"),
    )
    
    assert item.product_name == "Test Product"
    assert item.sku == "SKU123"
    assert item.quantity == Decimal("2")
    assert item.unit_price.amount == Decimal("10.00")
    assert item.line_total.amount == Decimal("20.00")
    assert item.discount_amount.amount == Decimal("0")


def test_receipt_line_item_with_discount():
    """Test receipt line item with discount."""
    item = ReceiptLineItem(
        product_name="Discounted Product",
        sku="SKU456",
        quantity=Decimal("1"),
        unit_price=Money(Decimal("50.00"), "USD"),
        line_total=Money(Decimal("40.00"), "USD"),
        discount_amount=Money(Decimal("10.00"), "USD"),
    )
    
    assert item.discount_amount.amount == Decimal("10.00")


def test_receipt_line_item_invalid_quantity():
    """Test that negative quantity raises error."""
    with pytest.raises(ValueError, match="Quantity must be positive"):
        ReceiptLineItem(
            product_name="Product",
            sku="SKU",
            quantity=Decimal("0"),
            unit_price=Money(Decimal("10.00"), "USD"),
            line_total=Money(Decimal("0"), "USD"),
        )


def test_create_receipt_payment():
    """Test creating a receipt payment."""
    payment = ReceiptPayment(
        payment_method="card",
        amount=Money(Decimal("50.00"), "USD"),
        reference_number="REF123",
        card_last_four="1234",
    )
    
    assert payment.payment_method == "card"
    assert payment.amount.amount == Decimal("50.00")
    assert payment.reference_number == "REF123"
    assert payment.card_last_four == "1234"


def test_create_receipt_totals():
    """Test creating receipt totals."""
    totals = ReceiptTotals(
        subtotal=Money(Decimal("100.00"), "USD"),
        tax_amount=Money(Decimal("8.00"), "USD"),
        discount_amount=Money(Decimal("10.00"), "USD"),
        total=Money(Decimal("98.00"), "USD"),
        amount_paid=Money(Decimal("100.00"), "USD"),
        change_given=Money(Decimal("2.00"), "USD"),
    )
    
    assert totals.subtotal.amount == Decimal("100.00")
    assert totals.tax_amount.amount == Decimal("8.00")
    assert totals.discount_amount.amount == Decimal("10.00")
    assert totals.total.amount == Decimal("98.00")
    assert totals.change_given.amount == Decimal("2.00")


def test_create_receipt():
    """Test creating a receipt."""
    line_items = [
        ReceiptLineItem(
            product_name="Product 1",
            sku="SKU001",
            quantity=Decimal("2"),
            unit_price=Money(Decimal("25.00"), "USD"),
            line_total=Money(Decimal("50.00"), "USD"),
        ),
        ReceiptLineItem(
            product_name="Product 2",
            sku="SKU002",
            quantity=Decimal("1"),
            unit_price=Money(Decimal("50.00"), "USD"),
            line_total=Money(Decimal("50.00"), "USD"),
        ),
    ]
    
    payments = [
        ReceiptPayment(
            payment_method="card",
            amount=Money(Decimal("108.00"), "USD"),
        )
    ]
    
    totals = ReceiptTotals(
        subtotal=Money(Decimal("100.00"), "USD"),
        tax_amount=Money(Decimal("8.00"), "USD"),
        discount_amount=Money(Decimal("0"), "USD"),
        total=Money(Decimal("108.00"), "USD"),
        amount_paid=Money(Decimal("108.00"), "USD"),
    )
    
    receipt = Receipt.create(
        sale_id="01SALE123",
        receipt_number="RCP-001",
        store_name="Test Store",
        store_address="123 Main St\nAnytown, ST 12345",
        store_phone="555-1234",
        cashier_name="John Doe",
        line_items=line_items,
        payments=payments,
        totals=totals,
        sale_date=datetime(2025, 12, 6, 10, 30, 0),
        tax_rate=Decimal("8.0"),
    )
    
    assert receipt.sale_id == "01SALE123"
    assert receipt.receipt_number == "RCP-001"
    assert receipt.store_name == "Test Store"
    assert receipt.cashier_name == "John Doe"
    assert len(receipt.line_items) == 2
    assert len(receipt.payments) == 1
    assert receipt.format_type == "thermal"  # Default


def test_receipt_with_customer():
    """Test creating receipt with customer information."""
    line_items = [
        ReceiptLineItem(
            product_name="Product",
            sku="SKU",
            quantity=Decimal("1"),
            unit_price=Money(Decimal("10.00"), "USD"),
            line_total=Money(Decimal("10.00"), "USD"),
        )
    ]
    
    payments = [
        ReceiptPayment(
            payment_method="cash",
            amount=Money(Decimal("10.80"), "USD"),
        )
    ]
    
    totals = ReceiptTotals(
        subtotal=Money(Decimal("10.00"), "USD"),
        tax_amount=Money(Decimal("0.80"), "USD"),
        discount_amount=Money(Decimal("0"), "USD"),
        total=Money(Decimal("10.80"), "USD"),
        amount_paid=Money(Decimal("10.80"), "USD"),
    )
    
    receipt = Receipt.create(
        sale_id="01SALE456",
        receipt_number="RCP-002",
        store_name="Store",
        store_address="Address",
        store_phone="555-0000",
        cashier_name="Jane Doe",
        customer_name="Alice Smith",
        customer_email="alice@example.com",
        line_items=line_items,
        payments=payments,
        totals=totals,
        sale_date=datetime.utcnow(),
        tax_rate=Decimal("8.0"),
    )
    
    assert receipt.customer_name == "Alice Smith"
    assert receipt.customer_email == "alice@example.com"


def test_receipt_a4_format():
    """Test creating receipt in A4 format."""
    line_items = [
        ReceiptLineItem(
            product_name="Product",
            sku="SKU",
            quantity=Decimal("1"),
            unit_price=Money(Decimal("10.00"), "USD"),
            line_total=Money(Decimal("10.00"), "USD"),
        )
    ]
    
    payments = [
        ReceiptPayment(
            payment_method="card",
            amount=Money(Decimal("10.80"), "USD"),
        )
    ]
    
    totals = ReceiptTotals(
        subtotal=Money(Decimal("10.00"), "USD"),
        tax_amount=Money(Decimal("0.80"), "USD"),
        discount_amount=Money(Decimal("0"), "USD"),
        total=Money(Decimal("10.80"), "USD"),
        amount_paid=Money(Decimal("10.80"), "USD"),
    )
    
    receipt = Receipt.create(
        sale_id="01SALE789",
        receipt_number="RCP-003",
        store_name="Store",
        store_address="Address",
        store_phone="555-0000",
        cashier_name="Bob Jones",
        line_items=line_items,
        payments=payments,
        totals=totals,
        sale_date=datetime.utcnow(),
        tax_rate=Decimal("8.0"),
        format_type="a4",
    )
    
    assert receipt.format_type == "a4"


def test_receipt_calculate_total_quantity():
    """Test calculating total quantity."""
    line_items = [
        ReceiptLineItem(
            product_name="Product 1",
            sku="SKU1",
            quantity=Decimal("2"),
            unit_price=Money(Decimal("10.00"), "USD"),
            line_total=Money(Decimal("20.00"), "USD"),
        ),
        ReceiptLineItem(
            product_name="Product 2",
            sku="SKU2",
            quantity=Decimal("3"),
            unit_price=Money(Decimal("5.00"), "USD"),
            line_total=Money(Decimal("15.00"), "USD"),
        ),
    ]
    
    payments = [
        ReceiptPayment(
            payment_method="cash",
            amount=Money(Decimal("37.80"), "USD"),
        )
    ]
    
    totals = ReceiptTotals(
        subtotal=Money(Decimal("35.00"), "USD"),
        tax_amount=Money(Decimal("2.80"), "USD"),
        discount_amount=Money(Decimal("0"), "USD"),
        total=Money(Decimal("37.80"), "USD"),
        amount_paid=Money(Decimal("37.80"), "USD"),
    )
    
    receipt = Receipt.create(
        sale_id="01SALE999",
        receipt_number="RCP-004",
        store_name="Store",
        store_address="Address",
        store_phone="555-0000",
        cashier_name="Cashier",
        line_items=line_items,
        payments=payments,
        totals=totals,
        sale_date=datetime.utcnow(),
        tax_rate=Decimal("8.0"),
    )
    
    total_qty = receipt.calculate_total_quantity()
    assert total_qty == Decimal("5")


def test_receipt_get_primary_payment_method():
    """Test getting primary payment method."""
    line_items = [
        ReceiptLineItem(
            product_name="Product",
            sku="SKU",
            quantity=Decimal("1"),
            unit_price=Money(Decimal("100.00"), "USD"),
            line_total=Money(Decimal("100.00"), "USD"),
        )
    ]
    
    payments = [
        ReceiptPayment(
            payment_method="card",
            amount=Money(Decimal("80.00"), "USD"),
        ),
        ReceiptPayment(
            payment_method="cash",
            amount=Money(Decimal("28.00"), "USD"),
        ),
    ]
    
    totals = ReceiptTotals(
        subtotal=Money(Decimal("100.00"), "USD"),
        tax_amount=Money(Decimal("8.00"), "USD"),
        discount_amount=Money(Decimal("0"), "USD"),
        total=Money(Decimal("108.00"), "USD"),
        amount_paid=Money(Decimal("108.00"), "USD"),
    )
    
    receipt = Receipt.create(
        sale_id="01SALE888",
        receipt_number="RCP-005",
        store_name="Store",
        store_address="Address",
        store_phone="555-0000",
        cashier_name="Cashier",
        line_items=line_items,
        payments=payments,
        totals=totals,
        sale_date=datetime.utcnow(),
        tax_rate=Decimal("8.0"),
    )
    
    primary = receipt.get_primary_payment_method()
    assert primary == "card"  # Largest amount


def test_receipt_no_line_items():
    """Test that receipt without line items raises error."""
    payments = [
        ReceiptPayment(
            payment_method="cash",
            amount=Money(Decimal("10.00"), "USD"),
        )
    ]
    
    totals = ReceiptTotals(
        subtotal=Money(Decimal("10.00"), "USD"),
        tax_amount=Money(Decimal("0"), "USD"),
        discount_amount=Money(Decimal("0"), "USD"),
        total=Money(Decimal("10.00"), "USD"),
        amount_paid=Money(Decimal("10.00"), "USD"),
    )
    
    with pytest.raises(ValueError, match="at least one line item"):
        Receipt.create(
            sale_id="01SALE",
            receipt_number="RCP",
            store_name="Store",
            store_address="Address",
            store_phone="Phone",
            cashier_name="Cashier",
            line_items=[],
            payments=payments,
            totals=totals,
            sale_date=datetime.utcnow(),
            tax_rate=Decimal("8.0"),
        )


def test_receipt_no_payments():
    """Test that receipt without payments raises error."""
    line_items = [
        ReceiptLineItem(
            product_name="Product",
            sku="SKU",
            quantity=Decimal("1"),
            unit_price=Money(Decimal("10.00"), "USD"),
            line_total=Money(Decimal("10.00"), "USD"),
        )
    ]
    
    totals = ReceiptTotals(
        subtotal=Money(Decimal("10.00"), "USD"),
        tax_amount=Money(Decimal("0"), "USD"),
        discount_amount=Money(Decimal("0"), "USD"),
        total=Money(Decimal("10.00"), "USD"),
        amount_paid=Money(Decimal("10.00"), "USD"),
    )
    
    with pytest.raises(ValueError, match="at least one payment"):
        Receipt.create(
            sale_id="01SALE",
            receipt_number="RCP",
            store_name="Store",
            store_address="Address",
            store_phone="Phone",
            cashier_name="Cashier",
            line_items=line_items,
            payments=[],
            totals=totals,
            sale_date=datetime.utcnow(),
            tax_rate=Decimal("8.0"),
        )


def test_receipt_invalid_format_type():
    """Test that invalid format type raises error."""
    line_items = [
        ReceiptLineItem(
            product_name="Product",
            sku="SKU",
            quantity=Decimal("1"),
            unit_price=Money(Decimal("10.00"), "USD"),
            line_total=Money(Decimal("10.00"), "USD"),
        )
    ]
    
    payments = [
        ReceiptPayment(
            payment_method="cash",
            amount=Money(Decimal("10.00"), "USD"),
        )
    ]
    
    totals = ReceiptTotals(
        subtotal=Money(Decimal("10.00"), "USD"),
        tax_amount=Money(Decimal("0"), "USD"),
        discount_amount=Money(Decimal("0"), "USD"),
        total=Money(Decimal("10.00"), "USD"),
        amount_paid=Money(Decimal("10.00"), "USD"),
    )
    
    with pytest.raises(ValueError, match="Format type must be 'thermal' or 'a4'"):
        Receipt.create(
            sale_id="01SALE",
            receipt_number="RCP",
            store_name="Store",
            store_address="Address",
            store_phone="Phone",
            cashier_name="Cashier",
            line_items=line_items,
            payments=payments,
            totals=totals,
            sale_date=datetime.utcnow(),
            tax_rate=Decimal("8.0"),
            format_type="invalid",
        )
