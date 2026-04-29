"""Receipt domain entities."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.domain.common.identifiers import generate_ulid
from app.domain.common.money import Money


@dataclass(frozen=True)
class ReceiptBranding:
    """Branding configuration for receipt."""

    logo_url: Optional[str] = None
    company_name: Optional[str] = None
    primary_color: str = "#1976D2"
    secondary_color: str = "#424242"
    tagline: Optional[str] = None
    show_logo_on_receipt: bool = True


@dataclass(frozen=True)
class ReceiptCurrencyConfig:
    """Currency formatting for receipt."""

    code: str = "USD"
    symbol: str = "$"
    symbol_position: str = "before"  # before or after
    decimal_places: int = 2
    thousand_separator: str = ","
    decimal_separator: str = "."

    def format_amount(self, amount: Decimal) -> str:
        """Format amount according to currency settings."""
        # Format number with separators
        amount_str = f"{amount:,.{self.decimal_places}f}"
        if self.thousand_separator != ",":
            amount_str = amount_str.replace(",", "§")
        if self.decimal_separator != ".":
            amount_str = amount_str.replace(".", self.decimal_separator)
        if self.thousand_separator != ",":
            amount_str = amount_str.replace("§", self.thousand_separator)

        if self.symbol_position == "after":
            return f"{amount_str} {self.symbol}"
        return f"{self.symbol}{amount_str}"


@dataclass(frozen=True)
class ReceiptLineItem:
    """Line item on a receipt."""

    product_name: str
    sku: str
    quantity: Decimal
    unit_price: Money
    line_total: Money
    discount_amount: Money = field(default_factory=lambda: Money(Decimal("0"), "USD"))

    def __post_init__(self) -> None:
        """Validate line item."""
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self.unit_price.amount < 0:
            raise ValueError("Unit price cannot be negative")
        if self.line_total.amount < 0:
            raise ValueError("Line total cannot be negative")


@dataclass(frozen=True)
class ReceiptPayment:
    """Payment information on a receipt."""

    payment_method: str  # cash, card, gift_card, etc.
    amount: Money
    reference_number: Optional[str] = None
    card_last_four: Optional[str] = None


@dataclass(frozen=True)
class ReceiptTotals:
    """Totals section of a receipt."""

    subtotal: Money
    tax_amount: Money
    discount_amount: Money
    total: Money
    amount_paid: Money
    change_given: Money = field(default_factory=lambda: Money(Decimal("0"), "USD"))

    def __post_init__(self) -> None:
        """Validate totals."""
        if self.subtotal.amount < 0:
            raise ValueError("Subtotal cannot be negative")
        if self.tax_amount.amount < 0:
            raise ValueError("Tax amount cannot be negative")
        if self.discount_amount.amount < 0:
            raise ValueError("Discount amount cannot be negative")
        if self.total.amount < 0:
            raise ValueError("Total cannot be negative")


@dataclass
class Receipt:
    """Receipt aggregate root."""

    id: str
    sale_id: str
    receipt_number: str
    store_name: str
    store_address: str
    store_phone: str
    store_tax_id: Optional[str]
    
    cashier_name: str
    customer_name: Optional[str]
    customer_email: Optional[str]
    
    line_items: list[ReceiptLineItem]
    payments: list[ReceiptPayment]
    totals: ReceiptTotals
    
    sale_date: datetime
    tax_rate: Decimal
    
    notes: Optional[str] = None
    footer_message: Optional[str] = "Thank you for your business!"
    
    format_type: str = "thermal"  # thermal or a4
    locale: str = "en_US"
    
    # Branding & currency configuration (optional - uses tenant settings if available)
    branding: Optional[ReceiptBranding] = None
    currency_config: Optional[ReceiptCurrencyConfig] = None
    invoice_prefix: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1

    def __post_init__(self) -> None:
        """Validate receipt."""
        if not self.line_items:
            raise ValueError("Receipt must have at least one line item")
        if not self.payments:
            raise ValueError("Receipt must have at least one payment")
        if self.format_type not in ("thermal", "a4"):
            raise ValueError("Format type must be 'thermal' or 'a4'")

    def format_amount(self, amount: Decimal) -> str:
        """Format an amount using the receipt's currency config."""
        if self.currency_config:
            return self.currency_config.format_amount(amount)
        return f"${amount:,.2f}"

    @classmethod
    def create(
        cls,
        sale_id: str,
        receipt_number: str,
        store_name: str,
        store_address: str,
        store_phone: str,
        cashier_name: str,
        line_items: list[ReceiptLineItem],
        payments: list[ReceiptPayment],
        totals: ReceiptTotals,
        sale_date: datetime,
        tax_rate: Decimal,
        store_tax_id: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_email: Optional[str] = None,
        notes: Optional[str] = None,
        footer_message: Optional[str] = "Thank you for your business!",
        format_type: str = "thermal",
        locale: str = "en_US",
        branding: Optional[ReceiptBranding] = None,
        currency_config: Optional[ReceiptCurrencyConfig] = None,
        invoice_prefix: Optional[str] = None,
    ) -> "Receipt":
        """Create a new receipt."""
        return cls(
            id=generate_ulid(),
            sale_id=sale_id,
            receipt_number=receipt_number,
            store_name=store_name,
            store_address=store_address,
            store_phone=store_phone,
            store_tax_id=store_tax_id,
            cashier_name=cashier_name,
            customer_name=customer_name,
            customer_email=customer_email,
            line_items=line_items,
            payments=payments,
            totals=totals,
            sale_date=sale_date,
            tax_rate=tax_rate,
            notes=notes,
            footer_message=footer_message,
            format_type=format_type,
            locale=locale,
            branding=branding,
            currency_config=currency_config,
            invoice_prefix=invoice_prefix,
        )

    def calculate_total_quantity(self) -> Decimal:
        """Calculate total quantity of items."""
        return sum(item.quantity for item in self.line_items)

    def get_primary_payment_method(self) -> str:
        """Get the primary payment method (largest amount)."""
        if not self.payments:
            return "unknown"
        return max(self.payments, key=lambda p: p.amount.amount).payment_method
