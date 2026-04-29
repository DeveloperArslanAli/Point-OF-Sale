"""
Payment API schemas (DTOs).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class PaymentBase(BaseModel):
    """Base payment schema."""

    amount: Decimal = Field(gt=0, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)


class ProcessCashPaymentRequest(PaymentBase):
    """Request to process cash payment."""

    sale_id: str = Field(min_length=26, max_length=26)


class ProcessCardPaymentRequest(PaymentBase):
    """Request to process card payment."""

    sale_id: str = Field(min_length=26, max_length=26)
    provider: str = Field(description="Payment provider: stripe, paypal, etc.")
    description: str = Field(min_length=1, max_length=500)
    customer_id: Optional[str] = Field(None, min_length=26, max_length=26)
    
    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate provider value."""
        allowed = ["stripe", "paypal", "square"]
        if v not in allowed:
            raise ValueError(f"Provider must be one of: {', '.join(allowed)}")
        return v


class CapturePaymentRequest(BaseModel):
    """Request to capture authorized payment."""

    payment_id: str = Field(min_length=26, max_length=26)
    amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2, description="Partial capture amount")


class RefundPaymentRequest(BaseModel):
    """Request to refund payment."""

    payment_id: str = Field(min_length=26, max_length=26)
    amount: Decimal = Field(gt=0, decimal_places=2)
    reason: Optional[str] = Field(None, max_length=500)


class PaymentResponse(BaseModel):
    """Payment response schema."""

    id: str
    sale_id: str
    method: str
    amount: Decimal
    currency: str
    status: str
    provider: str
    provider_transaction_id: Optional[str] = None
    card_last4: Optional[str] = None
    card_brand: Optional[str] = None
    authorized_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    refunded_amount: Decimal
    refunded_at: Optional[datetime] = None
    created_at: datetime
    created_by: str
    notes: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class CardPaymentResponse(PaymentResponse):
    """Card payment response with client secret."""

    client_secret: Optional[str] = Field(None, description="For client-side payment confirmation")


class PaymentListResponse(BaseModel):
    """List of payments response."""

    items: list[PaymentResponse]
    total: int
