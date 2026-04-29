"""
Promotion API schemas (DTOs).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class DiscountRuleSchema(BaseModel):
    """Discount rule schema."""

    discount_type: str = Field(description="percentage, fixed_amount, buy_x_get_y, free_shipping")
    value: Decimal = Field(gt=0, decimal_places=2)
    buy_quantity: int = Field(default=0, ge=0)
    get_quantity: int = Field(default=0, ge=0)
    min_purchase_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    max_discount_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    target: str = Field(default="order", description="order, category, product, customer")
    target_product_ids: list[str] = Field(default_factory=list)
    target_category_ids: list[str] = Field(default_factory=list)
    
    @field_validator("discount_type")
    @classmethod
    def validate_discount_type(cls, v: str) -> str:
        allowed = ["percentage", "fixed_amount", "buy_x_get_y", "free_shipping"]
        if v not in allowed:
            raise ValueError(f"Discount type must be one of: {', '.join(allowed)}")
        return v
    
    @field_validator("target")
    @classmethod
    def validate_target(cls, v: str) -> str:
        allowed = ["order", "category", "product", "customer"]
        if v not in allowed:
            raise ValueError(f"Target must be one of: {', '.join(allowed)}")
        return v


class CreatePromotionRequest(BaseModel):
    """Request to create a promotion."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    discount_type: str
    value: Decimal = Field(gt=0, decimal_places=2)
    start_date: datetime
    end_date: Optional[datetime] = None
    
    # Optional discount rule fields
    buy_quantity: int = Field(default=0, ge=0)
    get_quantity: int = Field(default=0, ge=0)
    min_purchase_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    max_discount_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    target: str = Field(default="order")
    target_product_ids: list[str] = Field(default_factory=list)
    target_category_ids: list[str] = Field(default_factory=list)
    
    # Promotion constraints
    usage_limit: Optional[int] = Field(None, gt=0)
    usage_limit_per_customer: Optional[int] = Field(None, gt=0)
    coupon_code: Optional[str] = Field(None, min_length=1, max_length=100)
    is_case_sensitive: bool = False
    customer_ids: list[str] = Field(default_factory=list)
    exclude_sale_items: bool = False
    can_combine: bool = False
    priority: int = Field(default=0, ge=0)


class UpdatePromotionRequest(BaseModel):
    """Request to update a promotion."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    end_date: Optional[datetime] = None
    usage_limit: Optional[int] = Field(None, gt=0)
    usage_limit_per_customer: Optional[int] = Field(None, gt=0)
    priority: Optional[int] = Field(None, ge=0)


class ApplyPromotionRequest(BaseModel):
    """Request to apply a promotion."""

    promotion_id: str = Field(min_length=26, max_length=26)
    subtotal: Decimal = Field(gt=0, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    quantity: int = Field(default=1, gt=0)
    customer_id: Optional[str] = Field(None, min_length=26, max_length=26)
    coupon_code: Optional[str] = Field(None, max_length=100)


class ValidateCouponRequest(BaseModel):
    """Request to validate a coupon code."""

    coupon_code: str = Field(min_length=1, max_length=100)
    customer_id: Optional[str] = Field(None, min_length=26, max_length=26)


class PromotionResponse(BaseModel):
    """Promotion response schema."""

    id: str
    name: str
    description: str
    discount_rule: DiscountRuleSchema
    status: str
    start_date: datetime
    end_date: Optional[datetime]
    usage_limit: Optional[int]
    usage_count: int
    usage_limit_per_customer: Optional[int]
    coupon_code: Optional[str]
    is_case_sensitive: bool
    customer_ids: list[str]
    exclude_sale_items: bool
    can_combine_with_other_promotions: bool
    priority: int
    created_at: datetime
    created_by: str
    
    model_config = ConfigDict(from_attributes=True)


class PromotionListResponse(BaseModel):
    """List of promotions response."""

    items: list[PromotionResponse]
    total: int


class DiscountCalculationResponse(BaseModel):
    """Discount calculation response."""

    promotion_id: str
    promotion_name: str
    discount_amount: Decimal
    currency: str
    original_amount: Decimal
    final_amount: Decimal
