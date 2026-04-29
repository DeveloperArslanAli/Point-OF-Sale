"""Cash drawer API schemas."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class OpenDrawerRequest(BaseModel):
    """Request to open a cash drawer."""

    terminal_id: str = Field(..., min_length=1, max_length=50, description="POS terminal identifier")
    opening_amount: Decimal = Field(..., ge=0, description="Starting cash amount")
    currency: str = Field(default="USD", min_length=3, max_length=3)


class CloseDrawerRequest(BaseModel):
    """Request to close a cash drawer."""

    session_id: str = Field(..., min_length=1, max_length=26, description="Drawer session ID")
    closing_amount: Decimal = Field(..., ge=0, description="Actual counted cash amount")
    notes: str | None = Field(default=None, max_length=500, description="Closing notes")


class RecordMovementRequest(BaseModel):
    """Request to record a cash movement."""

    session_id: str = Field(..., min_length=1, max_length=26, description="Drawer session ID")
    movement_type: str = Field(
        ...,
        description="Type: drop, pickup, pay_in, payout",
    )
    amount: Decimal = Field(..., gt=0, description="Movement amount")
    notes: str | None = Field(default=None, max_length=255, description="Movement notes")


class CashMovementOut(BaseModel):
    """Cash movement response."""

    id: str
    drawer_session_id: str
    movement_type: str
    amount: Decimal
    currency: str
    reason: str | None
    reference_id: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DrawerTotalsOut(BaseModel):
    """Drawer movement totals."""

    pay_in: Decimal
    payout: Decimal
    sales: Decimal
    change: Decimal
    refunds: Decimal
    net_cash_sales: Decimal


class CashDrawerSessionOut(BaseModel):
    """Cash drawer session response."""

    id: str
    terminal_id: str
    opened_by: str
    closed_by: str | None
    opening_amount: Decimal
    closing_amount: Decimal | None
    expected_balance: Decimal
    over_short: Decimal | None
    currency: str
    status: str
    opened_at: datetime
    closed_at: datetime | None
    version: int
    movements: list[CashMovementOut] = []
    totals: DrawerTotalsOut | None = None
    model_config = ConfigDict(from_attributes=True)


class DrawerSessionListOut(BaseModel):
    """Paginated list of drawer sessions."""

    items: list[CashDrawerSessionOut]
    total: int
    page: int
    limit: int
    pages: int
