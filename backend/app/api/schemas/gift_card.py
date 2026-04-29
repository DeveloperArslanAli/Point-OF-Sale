"""Gift card schemas."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class GiftCardPurchaseRequest(BaseModel):
    """Request to purchase a gift card."""
    
    amount: Decimal = Field(..., gt=0, description="Initial balance amount")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="Currency code")
    customer_id: str | None = Field(None, description="Optional customer ID who purchased the card")
    validity_days: int = Field(default=365, gt=0, le=3650, description="Days until expiry (max 10 years)")


class GiftCardActivateRequest(BaseModel):
    """Request to activate a gift card."""
    
    code: str = Field(..., min_length=15, max_length=20, description="Gift card code")


class GiftCardRedeemRequest(BaseModel):
    """Request to redeem value from a gift card."""
    
    code: str = Field(..., min_length=15, max_length=20, description="Gift card code")
    amount: Decimal = Field(..., gt=0, description="Amount to redeem")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="Currency code")


class GiftCardOut(BaseModel):
    """Gift card response."""
    
    id: str
    code: str
    initial_balance: Decimal
    current_balance: Decimal
    currency: str
    status: str
    issued_date: datetime
    expiry_date: datetime | None
    customer_id: str | None
    created_at: datetime
    updated_at: datetime
    version: int
    model_config = ConfigDict(from_attributes=True)


class GiftCardBalanceOut(BaseModel):
    """Gift card balance check response."""
    
    code: str
    current_balance: Decimal
    currency: str
    status: str
    is_usable: bool
    expiry_date: datetime | None
