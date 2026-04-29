from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.common.errors import ValidationError
from app.domain.common.identifiers import new_ulid
from app.domain.common.money import Money


@dataclass(slots=True)
class SalePayment:
    """Individual payment within a sale (for split payments)."""
    
    id: str
    payment_method: str  # cash, card, gift_card, etc.
    amount: Money
    reference_number: str | None = None
    card_last_four: str | None = None
    gift_card_id: str | None = None
    gift_card_code: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def create(
        *,
        payment_method: str,
        amount: Decimal,
        currency: str = "USD",
        reference_number: str | None = None,
        card_last_four: str | None = None,
        gift_card_id: str | None = None,
        gift_card_code: str | None = None,
    ) -> SalePayment:
        """Create a new sale payment."""
        if not payment_method:
            raise ValidationError("payment_method is required", code="sale_payment.invalid_method")
        money_amount = Money(amount, currency)
        if money_amount.amount <= Decimal("0"):
            raise ValidationError("payment amount must be positive", code="sale_payment.invalid_amount")
        
        return SalePayment(
            id=new_ulid(),
            payment_method=payment_method.lower(),
            amount=money_amount,
            reference_number=reference_number,
            card_last_four=card_last_four,
            gift_card_id=gift_card_id,
            gift_card_code=gift_card_code,
        )


@dataclass(slots=True)
class SaleItem:
    id: str
    product_id: str
    quantity: int
    unit_price: Money
    line_total: Money

    @staticmethod
    def create(
        *,
        product_id: str,
        quantity: int,
        unit_price: Decimal,
        currency: str = "USD",
    ) -> SaleItem:
        if not product_id:
            raise ValidationError("product_id is required", code="sale_item.invalid_product_id")
        if quantity <= 0:
            raise ValidationError("quantity must be positive", code="sale_item.invalid_quantity")
        if unit_price <= Decimal("0"):
            raise ValidationError("unit_price must be positive", code="sale_item.invalid_unit_price")
        price = Money(unit_price, currency)
        return SaleItem(
            id=new_ulid(),
            product_id=product_id,
            quantity=quantity,
            unit_price=price,
            line_total=price.multiply(quantity),
        )


@dataclass(slots=True)
class Sale:
    id: str
    currency: str
    items: list[SaleItem] = field(default_factory=list)
    payments: list[SalePayment] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None
    customer_id: str | None = None
    shift_id: str | None = None

    @staticmethod
    def start(currency: str = "USD", *, customer_id: str | None = None, shift_id: str | None = None) -> Sale:
        if not currency or len(currency) != 3:
            raise ValidationError("currency must be a 3-letter code", code="sale.invalid_currency")
        return Sale(id=new_ulid(), currency=currency.upper(), customer_id=customer_id, shift_id=shift_id)

    def add_item(self, item: SaleItem) -> None:
        if self.closed_at is not None:
            raise ValidationError("sale is already closed", code="sale.already_closed")
        if item.unit_price.currency != self.currency:
            raise ValidationError("item currency mismatch", code="sale.currency_mismatch")
        self.items.append(item)

    def add_line(
        self,
        *,
        product_id: str,
        quantity: int,
        unit_price: Decimal,
    ) -> SaleItem:
        item = SaleItem.create(product_id=product_id, quantity=quantity, unit_price=unit_price, currency=self.currency)
        self.add_item(item)
        return item

    def close(self) -> None:
        if not self.items:
            raise ValidationError("sale must have at least one item", code="sale.empty")
        if self.closed_at is not None:
            raise ValidationError("sale already closed", code="sale.already_closed")
        self.validate_payments()
        self.closed_at = datetime.now(UTC)

    def add_payment(self, payment: SalePayment) -> None:
        """Add a payment to the sale."""
        if payment.amount.currency != self.currency:
            raise ValidationError("payment currency mismatch", code="sale.currency_mismatch")
        self.payments.append(payment)

    def validate_payments(self) -> None:
        """Validate that total payments equal sale total."""
        if not self.payments:
            raise ValidationError("sale must have at least one payment", code="sale.no_payments")
        
        total_paid = Money(Decimal("0"), self.currency)
        for payment in self.payments:
            total_paid = total_paid.add(payment.amount)
        
        sale_total = self.total_amount
        if total_paid.amount != sale_total.amount:
            raise ValidationError(
                f"payment total ({total_paid.amount}) does not match sale total ({sale_total.amount})",
                code="sale.payment_mismatch"
            )

    def assign_customer(self, customer_id: str | None) -> None:
        self.customer_id = customer_id

    def assign_shift(self, shift_id: str | None) -> None:
        """Assign a shift to this sale."""
        self.shift_id = shift_id

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None

    @property
    def total_amount(self) -> Money:
        total = Money(Decimal("0"), self.currency)
        for item in self.items:
            total = total.add(item.line_total)
        return total

    @property
    def total_paid(self) -> Money:
        """Calculate total amount paid across all payments."""
        total = Money(Decimal("0"), self.currency)
        for payment in self.payments:
            total = total.add(payment.amount)
        return total

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items)

    def iter_items(self) -> Iterable[SaleItem]:
        return iter(self.items)
