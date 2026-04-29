"""Pydantic schemas for customer loyalty API."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LoyaltyEnrollRequest(BaseModel):
    """Request to enroll customer in loyalty program."""

    customer_id: str = Field(min_length=26, max_length=26)


class LoyaltyEnrollResponse(BaseModel):
    """Response after enrolling customer."""

    account_id: str
    customer_id: str
    current_points: int
    tier: str


class LoyaltyEarnPointsRequest(BaseModel):
    """Request to earn loyalty points."""

    customer_id: str = Field(min_length=26, max_length=26)
    amount: Decimal = Field(gt=0, description="Purchase amount in dollars")
    reference_id: str | None = Field(default=None, description="Sale ID or other reference")
    description: str = Field(default="", max_length=500)


class LoyaltyEarnPointsResponse(BaseModel):
    """Response after earning points."""

    transaction_id: str
    points_earned: int
    new_balance: int
    tier: str
    tier_changed: bool
    points_to_next_tier: int | None


class LoyaltyRedeemPointsRequest(BaseModel):
    """Request to redeem loyalty points."""

    customer_id: str = Field(min_length=26, max_length=26)
    points: int = Field(gt=0, description="Number of points to redeem")
    reference_id: str | None = Field(default=None, description="Sale ID or other reference")
    description: str = Field(default="", max_length=500)


class LoyaltyRedeemPointsResponse(BaseModel):
    """Response after redeeming points."""

    transaction_id: str
    points_redeemed: int
    discount_value: str
    new_balance: int


class LoyaltyTransactionOut(BaseModel):
    """Loyalty point transaction output."""

    id: str
    transaction_type: str
    points: int
    balance_after: int
    reference_id: str | None
    description: str
    created_at: datetime


class LoyaltyAccountOut(BaseModel):
    """Loyalty account output."""

    account_id: str
    customer_id: str
    current_points: int
    lifetime_points: int
    tier: str
    tier_discount_percentage: str
    tier_point_multiplier: str
    points_to_next_tier: int | None
    next_tier: str | None
    enrolled_at: datetime
    recent_transactions: list[LoyaltyTransactionOut]


class LoyaltyAccountSummaryOut(BaseModel):
    """Summary of loyalty account for listing."""

    account_id: str
    customer_id: str
    current_points: int
    tier: str


class LoyaltyAccountListOut(BaseModel):
    """Paginated list of loyalty accounts."""

    items: list[LoyaltyAccountSummaryOut]
    total: int
    page: int
    limit: int
