"""Shift API schemas."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class StartShiftRequest(BaseModel):
    """Request to start a shift."""

    terminal_id: str = Field(..., min_length=1, max_length=50, description="POS terminal identifier")
    drawer_session_id: str | None = Field(default=None, max_length=26, description="Optional linked drawer session")
    opening_cash: Decimal | None = Field(default=None, ge=0, description="Opening cash amount")
    currency: str = Field(default="USD", min_length=3, max_length=3)


class EndShiftRequest(BaseModel):
    """Request to end a shift."""

    shift_id: str = Field(..., min_length=1, max_length=26)
    closing_cash: Decimal | None = Field(default=None, ge=0, description="Closing cash amount")


class ShiftOut(BaseModel):
    """Shift response."""

    id: str
    user_id: str
    terminal_id: str
    drawer_session_id: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None
    opening_cash: Decimal | None
    closing_cash: Decimal | None
    total_sales: Decimal
    total_transactions: int
    cash_sales: Decimal
    card_sales: Decimal
    gift_card_sales: Decimal
    other_sales: Decimal
    total_refunds: Decimal
    refund_count: int
    net_sales: Decimal
    duration_minutes: int | None
    currency: str
    version: int
    model_config = ConfigDict(from_attributes=True)


class ShiftListOut(BaseModel):
    """Paginated list of shifts."""

    items: list[ShiftOut]
    total: int
    page: int
    limit: int
    pages: int
