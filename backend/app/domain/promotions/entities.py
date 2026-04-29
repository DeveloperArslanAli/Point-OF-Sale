"""
Promotion and discount domain entities.

Handles promotional rules, discount calculations, and coupon codes.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from app.domain.common.errors import ValidationError
from app.domain.common.money import Money


class DiscountType(str, Enum):
    """Type of discount calculation."""

    PERCENTAGE = "percentage"  # 10% off
    FIXED_AMOUNT = "fixed_amount"  # $5 off
    BUY_X_GET_Y = "buy_x_get_y"  # Buy 2 get 1 free
    FREE_SHIPPING = "free_shipping"  # Free shipping (future)


class PromotionStatus(str, Enum):
    """Promotion lifecycle status."""

    DRAFT = "draft"  # Being created
    ACTIVE = "active"  # Currently available
    SCHEDULED = "scheduled"  # Future start date
    EXPIRED = "expired"  # Past end date
    DISABLED = "disabled"  # Manually deactivated


class PromotionTarget(str, Enum):
    """What the promotion applies to."""

    ORDER = "order"  # Entire order/sale
    CATEGORY = "category"  # Specific categories
    PRODUCT = "product"  # Specific products
    CUSTOMER = "customer"  # Specific customers


@dataclass(slots=True)
class DiscountRule:
    """
    Discount calculation rule.

    Defines how discount is calculated and applied.
    """

    discount_type: DiscountType
    value: Decimal  # Percentage (0-100) or fixed amount
    
    # Buy X Get Y parameters
    buy_quantity: int = 0  # X in "Buy X Get Y"
    get_quantity: int = 0  # Y in "Buy X Get Y"
    
    # Constraints
    min_purchase_amount: Optional[Decimal] = None
    max_discount_amount: Optional[Decimal] = None
    
    # Target
    target: PromotionTarget = PromotionTarget.ORDER
    target_product_ids: list[str] = field(default_factory=list)
    target_category_ids: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate rule on initialization."""
        if self.discount_type == DiscountType.PERCENTAGE:
            if not (Decimal("0") <= self.value <= Decimal("100")):
                raise ValidationError("Percentage must be between 0 and 100")
        
        elif self.discount_type == DiscountType.FIXED_AMOUNT:
            if self.value <= Decimal("0"):
                raise ValidationError("Fixed amount must be positive")
        
        elif self.discount_type == DiscountType.BUY_X_GET_Y:
            if self.buy_quantity <= 0 or self.get_quantity <= 0:
                raise ValidationError("Buy and get quantities must be positive")
        
        if self.min_purchase_amount and self.min_purchase_amount < Decimal("0"):
            raise ValidationError("Minimum purchase amount cannot be negative")

    def calculate_discount(
        self,
        subtotal: Money,
        quantity: int = 1,
    ) -> Money:
        """
        Calculate discount amount.

        Args:
            subtotal: Order/line item subtotal
            quantity: Item quantity (for Buy X Get Y)

        Returns:
            Discount amount as Money
        """
        # Check minimum purchase requirement
        if self.min_purchase_amount and subtotal.amount < self.min_purchase_amount:
            return Money(Decimal("0"), subtotal.currency)
        
        discount_amount = Decimal("0")
        
        if self.discount_type == DiscountType.PERCENTAGE:
            discount_amount = subtotal.amount * (self.value / Decimal("100"))
        
        elif self.discount_type == DiscountType.FIXED_AMOUNT:
            discount_amount = self.value
        
        elif self.discount_type == DiscountType.BUY_X_GET_Y:
            # Calculate number of free items
            if quantity >= self.buy_quantity:
                free_items = (quantity // self.buy_quantity) * self.get_quantity
                unit_price = subtotal.amount / Decimal(quantity)
                discount_amount = unit_price * Decimal(free_items)
        
        # Apply maximum discount cap
        if self.max_discount_amount:
            discount_amount = min(discount_amount, self.max_discount_amount)
        
        # Cannot exceed subtotal
        discount_amount = min(discount_amount, subtotal.amount)
        
        return Money(discount_amount, subtotal.currency)


@dataclass(slots=True)
class Promotion:
    """
    Promotion aggregate.

    Represents a promotional campaign with discount rules and constraints.
    """

    id: str
    name: str
    description: str
    discount_rule: DiscountRule
    status: PromotionStatus
    
    # Validity period
    start_date: datetime
    end_date: Optional[datetime] = None
    
    # Usage limits
    usage_limit: Optional[int] = None  # Total uses allowed
    usage_count: int = 0  # Current usage count
    usage_limit_per_customer: Optional[int] = None
    
    # Coupon code (optional)
    coupon_code: Optional[str] = None
    is_case_sensitive: bool = False
    
    # Targeting
    customer_ids: list[str] = field(default_factory=list)  # Specific customers
    exclude_sale_items: bool = False  # Exclude already discounted items
    
    # Combinability
    can_combine_with_other_promotions: bool = False
    
    # Priority (higher = applied first)
    priority: int = 0
    
    # Audit
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    updated_at: datetime = field(default_factory=datetime.utcnow)
    updated_by: str = ""
    
    version: int = 1

    def __post_init__(self):
        """Validate promotion on initialization."""
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date must be after start date")
        
        if self.usage_limit and self.usage_limit < 0:
            raise ValidationError("Usage limit cannot be negative")
        
        if self.usage_limit_per_customer and self.usage_limit_per_customer < 0:
            raise ValidationError("Per-customer usage limit cannot be negative")

    def is_active(self) -> bool:
        """Check if promotion is currently active."""
        if self.status != PromotionStatus.ACTIVE:
            return False
        
        def _ensure_utc(dt: datetime | None) -> datetime | None:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)

        now = datetime.now(UTC)
        start_date = _ensure_utc(self.start_date)
        end_date = _ensure_utc(self.end_date)
        
        # Check start date
        if start_date and now < start_date:
            return False
        
        # Check end date
        if end_date and now > end_date:
            return False
        
        # Check usage limit
        if self.usage_limit and self.usage_count >= self.usage_limit:
            return False
        
        return True

    def can_apply_to_customer(
        self,
        customer_id: Optional[str],
        customer_usage_count: int = 0,
    ) -> bool:
        """
        Check if promotion can be applied to customer.

        Args:
            customer_id: Customer identifier (None for anonymous)
            customer_usage_count: How many times customer used this promotion

        Returns:
            True if customer can use promotion
        """
        # Check customer-specific promotions
        if self.customer_ids and (not customer_id or customer_id not in self.customer_ids):
            return False
        
        # Check per-customer usage limit
        if self.usage_limit_per_customer and customer_usage_count >= self.usage_limit_per_customer:
            return False
        
        return True

    def validate_coupon_code(self, code: str) -> bool:
        """
        Validate coupon code.

        Args:
            code: Coupon code to validate

        Returns:
            True if code matches
        """
        if not self.coupon_code:
            return True  # No code required
        
        if self.is_case_sensitive:
            return code == self.coupon_code
        else:
            return code.upper() == self.coupon_code.upper()

    def apply_discount(
        self,
        subtotal: Money,
        quantity: int = 1,
        customer_id: Optional[str] = None,
        customer_usage_count: int = 0,
        coupon_code: Optional[str] = None,
    ) -> Money:
        """
        Apply promotion discount.

        Args:
            subtotal: Amount to discount
            quantity: Item quantity (for Buy X Get Y)
            customer_id: Customer identifier
            customer_usage_count: Customer's usage count
            coupon_code: Provided coupon code

        Returns:
            Discount amount

        Raises:
            ValidationError: If promotion cannot be applied
        """
        if not self.is_active():
            raise ValidationError("Promotion is not active")
        
        if not self.can_apply_to_customer(customer_id, customer_usage_count):
            raise ValidationError("Promotion cannot be applied to this customer")
        
        if self.coupon_code and not self.validate_coupon_code(coupon_code or ""):
            raise ValidationError("Invalid coupon code")
        
        return self.discount_rule.calculate_discount(subtotal, quantity)

    def increment_usage(self) -> None:
        """Increment usage count."""
        self.usage_count += 1
        self.updated_at = datetime.utcnow()
        self.version += 1

    def activate(self) -> None:
        """Activate promotion."""
        if self.status == PromotionStatus.DRAFT:
            self.status = PromotionStatus.ACTIVE
            self.updated_at = datetime.utcnow()
            self.version += 1

    def deactivate(self) -> None:
        """Deactivate promotion."""
        if self.status == PromotionStatus.ACTIVE:
            self.status = PromotionStatus.DISABLED
            self.updated_at = datetime.utcnow()
            self.version += 1

    def expire(self) -> None:
        """Mark promotion as expired."""
        self.status = PromotionStatus.EXPIRED
        self.updated_at = datetime.utcnow()
        self.version += 1


@dataclass(slots=True)
class AppliedDiscount:
    """
    Record of a discount applied to a sale.

    Tracks which promotion was used and the discount amount.
    """

    id: str
    promotion_id: str
    promotion_name: str
    discount_amount: Money
    coupon_code: Optional[str] = None
    applied_at: datetime = field(default_factory=datetime.utcnow)
