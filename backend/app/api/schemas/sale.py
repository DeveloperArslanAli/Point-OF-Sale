from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Sequence

from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.schemas.inventory import InventoryMovementOut
from app.domain.inventory import InventoryMovement
from app.domain.sales import Sale, SaleItem


class SaleLineCreate(BaseModel):
    product_id: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=Decimal("0"))


class SalePaymentCreate(BaseModel):
    """Schema for creating a payment within a sale."""
    payment_method: str = Field(min_length=1, description="Payment method (cash, card, gift_card, etc.)")
    amount: Decimal = Field(gt=Decimal("0"), description="Payment amount")
    reference_number: str | None = Field(default=None, description="Payment reference/transaction number")
    card_last_four: str | None = Field(default=None, min_length=4, max_length=4, description="Last 4 digits of card")
    gift_card_code: str | None = Field(
        default=None,
        min_length=15,
        max_length=20,
        description="Gift card code when using gift_card payment method",
    )

    @model_validator(mode="after")
    def validate_gift_card(self: "SalePaymentCreate") -> "SalePaymentCreate":
        if self.payment_method.lower() == "gift_card" and not self.gift_card_code:
            raise ValueError("gift_card_code is required when payment_method is gift_card")
        return self


class SaleCreate(BaseModel):
    currency: str = Field(default="USD", min_length=3, max_length=3)
    lines: list[SaleLineCreate]
    payments: list[SalePaymentCreate]
    customer_id: str | None = Field(default=None, min_length=1, max_length=26)
    shift_id: str | None = Field(default=None, min_length=1, max_length=26)

    @field_validator("lines")
    @classmethod
    def ensure_lines_present(cls, value: list[SaleLineCreate]) -> list[SaleLineCreate]:
        if not value:
            raise ValueError("Sale requires at least one line")
        return value

    @field_validator("payments")
    @classmethod
    def ensure_payments_present(cls, value: list[SalePaymentCreate]) -> list[SalePaymentCreate]:
        if not value:
            raise ValueError("Sale requires at least one payment")
        return value


class SaleItemOut(BaseModel):
    id: str
    product_id: str
    quantity: int
    returned_quantity: int = 0
    unit_price: str
    line_total: str

    @classmethod
    def from_domain(cls, item: SaleItem, returned_quantity: int = 0) -> SaleItemOut:
        return cls(
            id=item.id,
            product_id=item.product_id,
            quantity=item.quantity,
            returned_quantity=returned_quantity,
            unit_price=str(item.unit_price.amount),
            line_total=str(item.line_total.amount),
        )


class SalePaymentOut(BaseModel):
    """Schema for payment information in sale response."""
    payment_method: str
    amount: str
    reference_number: str | None
    card_last_four: str | None
    gift_card_id: str | None
    gift_card_code: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, payment: "SalePayment") -> "SalePaymentOut":
        from app.domain.sales.entities import SalePayment
        return cls(
            payment_method=payment.payment_method,
            amount=str(payment.amount.amount),
            reference_number=payment.reference_number,
            card_last_four=payment.card_last_four,
            gift_card_id=payment.gift_card_id,
            gift_card_code=payment.gift_card_code,
            created_at=payment.created_at,
        )


class SaleOut(BaseModel):
    id: str
    currency: str
    total_amount: str
    total_quantity: int
    created_at: datetime
    closed_at: datetime | None
    items: list[SaleItemOut]
    payments: list[SalePaymentOut]
    customer_id: str | None
    shift_id: str | None

    @classmethod
    def from_domain(cls, sale: Sale, returned_quantities: dict[str, int] | None = None) -> SaleOut:
        returned_quantities = returned_quantities or {}
        return cls(
            id=sale.id,
            currency=sale.currency,
            total_amount=str(sale.total_amount.amount),
            total_quantity=sale.total_quantity,
            created_at=sale.created_at,
            closed_at=sale.closed_at,
            items=[
                SaleItemOut.from_domain(item, returned_quantities.get(item.id, 0))
                for item in sale.iter_items()
            ],
            payments=[SalePaymentOut.from_domain(payment) for payment in sale.payments],
            customer_id=sale.customer_id,
            shift_id=sale.shift_id,
        )


class SaleRecordOut(BaseModel):
    sale: SaleOut
    movements: list[InventoryMovementOut]

    @classmethod
    def build(cls, sale: Sale, movements: Sequence[InventoryMovement]) -> SaleRecordOut:
        movement_out = [InventoryMovementOut.model_validate(m) for m in movements]
        return cls(sale=SaleOut.from_domain(sale), movements=movement_out)


class SalePageMetaOut(BaseModel):
    page: int
    limit: int
    total: int
    pages: int


class SaleListOut(BaseModel):
    items: list[SaleOut]
    meta: SalePageMetaOut
