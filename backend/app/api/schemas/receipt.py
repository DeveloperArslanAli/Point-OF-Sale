"""Receipt API schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class MoneySchema(BaseModel):
    """Money value object schema."""

    amount: Decimal = Field(..., description="Amount")
    currency: str = Field(..., description="Currency code (e.g., USD)")


class ReceiptLineItemSchema(BaseModel):
    """Receipt line item schema."""

    product_name: str = Field(..., description="Product name")
    sku: str = Field(..., description="Product SKU")
    quantity: Decimal = Field(..., description="Quantity")
    unit_price: MoneySchema = Field(..., description="Unit price")
    line_total: MoneySchema = Field(..., description="Line total")
    discount_amount: MoneySchema = Field(
        default=MoneySchema(amount=Decimal("0"), currency="USD"),
        description="Discount amount"
    )


class ReceiptPaymentSchema(BaseModel):
    """Receipt payment schema."""

    payment_method: str = Field(..., description="Payment method (cash, card, etc.)")
    amount: MoneySchema = Field(..., description="Payment amount")
    reference_number: Optional[str] = Field(None, description="Payment reference number")
    card_last_four: Optional[str] = Field(None, description="Last 4 digits of card")


class ReceiptTotalsSchema(BaseModel):
    """Receipt totals schema."""

    subtotal: MoneySchema = Field(..., description="Subtotal")
    tax_amount: MoneySchema = Field(..., description="Tax amount")
    discount_amount: MoneySchema = Field(..., description="Total discount")
    total: MoneySchema = Field(..., description="Total amount")
    amount_paid: MoneySchema = Field(..., description="Amount paid")
    change_given: MoneySchema = Field(
        default=MoneySchema(amount=Decimal("0"), currency="USD"),
        description="Change given"
    )


class CreateReceiptRequest(BaseModel):
    """Create receipt request."""

    sale_id: str = Field(..., description="Sale ID")
    receipt_number: str = Field(..., description="Receipt number")
    store_name: str = Field(..., description="Store name")
    store_address: str = Field(..., description="Store address")
    store_phone: str = Field(..., description="Store phone")
    store_tax_id: Optional[str] = Field(None, description="Store tax ID")
    
    cashier_name: str = Field(..., description="Cashier name")
    customer_name: Optional[str] = Field(None, description="Customer name")
    customer_email: Optional[str] = Field(None, description="Customer email")
    
    line_items: list[ReceiptLineItemSchema] = Field(..., description="Line items")
    payments: list[ReceiptPaymentSchema] = Field(..., description="Payments")
    totals: ReceiptTotalsSchema = Field(..., description="Totals")
    
    sale_date: datetime = Field(..., description="Sale date")
    tax_rate: Decimal = Field(..., description="Tax rate")
    
    notes: Optional[str] = Field(None, description="Receipt notes")
    footer_message: Optional[str] = Field(
        "Thank you for your business!",
        description="Footer message"
    )
    format_type: str = Field("thermal", description="Format type (thermal or a4)")
    locale: str = Field("en_US", description="Locale")


class ReceiptResponse(BaseModel):
    """Receipt response."""

    id: str = Field(..., description="Receipt ID")
    sale_id: str = Field(..., description="Sale ID")
    receipt_number: str = Field(..., description="Receipt number")
    store_name: str = Field(..., description="Store name")
    store_address: str = Field(..., description="Store address")
    store_phone: str = Field(..., description="Store phone")
    store_tax_id: Optional[str] = Field(None, description="Store tax ID")
    
    cashier_name: str = Field(..., description="Cashier name")
    customer_name: Optional[str] = Field(None, description="Customer name")
    customer_email: Optional[str] = Field(None, description="Customer email")
    
    line_items: list[ReceiptLineItemSchema] = Field(..., description="Line items")
    payments: list[ReceiptPaymentSchema] = Field(..., description="Payments")
    totals: ReceiptTotalsSchema = Field(..., description="Totals")
    
    sale_date: datetime = Field(..., description="Sale date")
    tax_rate: Decimal = Field(..., description="Tax rate")
    
    notes: Optional[str] = Field(None, description="Receipt notes")
    footer_message: Optional[str] = Field(None, description="Footer message")
    format_type: str = Field(..., description="Format type")
    locale: str = Field(..., description="Locale")
    
    created_at: datetime = Field(..., description="Created at")
    version: int = Field(..., description="Version")
    model_config = ConfigDict(from_attributes=True)


class ReceiptListResponse(BaseModel):
    """List of receipts response."""

    receipts: list[ReceiptResponse] = Field(..., description="List of receipts")
    total: int = Field(..., description="Total count")
