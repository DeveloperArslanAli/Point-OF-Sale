"""
Unit tests for Promotion entities.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.common.errors import ValidationError
from app.domain.common.money import Money
from app.domain.promotions.entities import (
    DiscountRule,
    DiscountType,
    Promotion,
    PromotionStatus,
    PromotionTarget,
)


def test_create_percentage_discount():
    """Test percentage discount calculation."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10"),  # 10% off
    )
    
    subtotal = Money(Decimal("100.00"), "USD")
    discount = rule.calculate_discount(subtotal)
    
    assert discount.amount == Decimal("10.00")


def test_create_fixed_amount_discount():
    """Test fixed amount discount calculation."""
    rule = DiscountRule(
        discount_type=DiscountType.FIXED_AMOUNT,
        value=Decimal("15.00"),  # $15 off
    )
    
    subtotal = Money(Decimal("100.00"), "USD")
    discount = rule.calculate_discount(subtotal)
    
    assert discount.amount == Decimal("15.00")


def test_buy_x_get_y_discount():
    """Test Buy X Get Y discount calculation."""
    rule = DiscountRule(
        discount_type=DiscountType.BUY_X_GET_Y,
        value=Decimal("0"),  # Value not used for BOGO
        buy_quantity=2,
        get_quantity=1,  # Buy 2 get 1 free
    )
    
    # 3 items at $10 each = $30 total, get 1 free ($10 off)
    subtotal = Money(Decimal("30.00"), "USD")
    discount = rule.calculate_discount(subtotal, quantity=3)
    
    assert discount.amount == Decimal("10.00")


def test_buy_x_get_y_multiple_sets():
    """Test Buy X Get Y with multiple qualifying sets."""
    rule = DiscountRule(
        discount_type=DiscountType.BUY_X_GET_Y,
        value=Decimal("0"),
        buy_quantity=2,
        get_quantity=1,
    )
    
    # 6 items = 3 sets of Buy 2 Get 1 = 3 free items
    subtotal = Money(Decimal("60.00"), "USD")  # 6 items * $10
    discount = rule.calculate_discount(subtotal, quantity=6)
    
    assert discount.amount == Decimal("30.00")  # 3 free items * $10


def test_minimum_purchase_requirement():
    """Test discount with minimum purchase requirement."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10"),
        min_purchase_amount=Decimal("50.00"),
    )
    
    # Below minimum
    subtotal1 = Money(Decimal("40.00"), "USD")
    discount1 = rule.calculate_discount(subtotal1)
    assert discount1.amount == Decimal("0.00")
    
    # Above minimum
    subtotal2 = Money(Decimal("60.00"), "USD")
    discount2 = rule.calculate_discount(subtotal2)
    assert discount2.amount == Decimal("6.00")


def test_maximum_discount_cap():
    """Test discount with maximum cap."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("50"),  # 50% off
        max_discount_amount=Decimal("20.00"),  # Max $20 off
    )
    
    # 50% of $100 = $50, but capped at $20
    subtotal = Money(Decimal("100.00"), "USD")
    discount = rule.calculate_discount(subtotal)
    
    assert discount.amount == Decimal("20.00")


def test_discount_cannot_exceed_subtotal():
    """Test discount is capped at subtotal amount."""
    rule = DiscountRule(
        discount_type=DiscountType.FIXED_AMOUNT,
        value=Decimal("50.00"),
    )
    
    subtotal = Money(Decimal("30.00"), "USD")
    discount = rule.calculate_discount(subtotal)
    
    assert discount.amount == Decimal("30.00")  # Capped at subtotal


def test_invalid_percentage():
    """Test invalid percentage value."""
    with pytest.raises(ValidationError, match="between 0 and 100"):
        DiscountRule(
            discount_type=DiscountType.PERCENTAGE,
            value=Decimal("150"),
        )


def test_invalid_buy_x_get_y():
    """Test invalid Buy X Get Y parameters."""
    with pytest.raises(ValidationError, match="must be positive"):
        DiscountRule(
            discount_type=DiscountType.BUY_X_GET_Y,
            value=Decimal("0"),
            buy_quantity=0,
            get_quantity=1,
        )


def test_create_promotion():
    """Test promotion creation."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("15"),
    )
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="Summer Sale",
        description="15% off everything",
        discount_rule=rule,
        status=PromotionStatus.DRAFT,
        start_date=datetime.utcnow(),
        created_by="user_123",
        updated_by="user_123",
    )
    
    assert promotion.id == "01JCTEST000000000000000001"
    assert promotion.name == "Summer Sale"
    assert promotion.status == PromotionStatus.DRAFT


def test_promotion_is_active():
    """Test promotion active status check."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10"),
    )
    
    now = datetime.utcnow()
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="Test Promotion",
        description="Test",
        discount_rule=rule,
        status=PromotionStatus.ACTIVE,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=1),
        created_by="user_123",
        updated_by="user_123",
    )
    
    assert promotion.is_active() is True


def test_promotion_not_active_wrong_status():
    """Test promotion not active due to status."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10"),
    )
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="Test Promotion",
        description="Test",
        discount_rule=rule,
        status=PromotionStatus.DRAFT,
        start_date=datetime.utcnow(),
        created_by="user_123",
        updated_by="user_123",
    )
    
    assert promotion.is_active() is False


def test_promotion_expired():
    """Test expired promotion."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10"),
    )
    
    now = datetime.utcnow()
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="Test Promotion",
        description="Test",
        discount_rule=rule,
        status=PromotionStatus.ACTIVE,
        start_date=now - timedelta(days=10),
        end_date=now - timedelta(days=1),  # Ended yesterday
        created_by="user_123",
        updated_by="user_123",
    )
    
    assert promotion.is_active() is False


def test_promotion_usage_limit():
    """Test promotion usage limit."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10"),
    )
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="Test Promotion",
        description="Test",
        discount_rule=rule,
        status=PromotionStatus.ACTIVE,
        start_date=datetime.utcnow(),
        usage_limit=5,
        usage_count=5,  # Reached limit
        created_by="user_123",
        updated_by="user_123",
    )
    
    assert promotion.is_active() is False


def test_coupon_code_validation():
    """Test coupon code validation."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10"),
    )
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="Test Promotion",
        description="Test",
        discount_rule=rule,
        status=PromotionStatus.ACTIVE,
        start_date=datetime.utcnow(),
        coupon_code="SAVE10",
        is_case_sensitive=False,
        created_by="user_123",
        updated_by="user_123",
    )
    
    assert promotion.validate_coupon_code("save10") is True
    assert promotion.validate_coupon_code("SAVE10") is True
    assert promotion.validate_coupon_code("INVALID") is False


def test_coupon_code_case_sensitive():
    """Test case-sensitive coupon code."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10"),
    )
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="Test Promotion",
        description="Test",
        discount_rule=rule,
        status=PromotionStatus.ACTIVE,
        start_date=datetime.utcnow(),
        coupon_code="SAVE10",
        is_case_sensitive=True,
        created_by="user_123",
        updated_by="user_123",
    )
    
    assert promotion.validate_coupon_code("SAVE10") is True
    assert promotion.validate_coupon_code("save10") is False


def test_apply_discount():
    """Test applying promotion discount."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("20"),
    )
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="Test Promotion",
        description="Test",
        discount_rule=rule,
        status=PromotionStatus.ACTIVE,
        start_date=datetime.utcnow(),
        created_by="user_123",
        updated_by="user_123",
    )
    
    subtotal = Money(Decimal("100.00"), "USD")
    discount = promotion.apply_discount(subtotal)
    
    assert discount.amount == Decimal("20.00")


def test_apply_discount_inactive_promotion():
    """Test applying inactive promotion fails."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("20"),
    )
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="Test Promotion",
        description="Test",
        discount_rule=rule,
        status=PromotionStatus.DRAFT,
        start_date=datetime.utcnow(),
        created_by="user_123",
        updated_by="user_123",
    )
    
    subtotal = Money(Decimal("100.00"), "USD")
    
    with pytest.raises(ValidationError, match="not active"):
        promotion.apply_discount(subtotal)


def test_customer_specific_promotion():
    """Test customer-specific promotion."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10"),
    )
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="VIP Discount",
        description="For VIP customers only",
        discount_rule=rule,
        status=PromotionStatus.ACTIVE,
        start_date=datetime.utcnow(),
        customer_ids=["customer_123", "customer_456"],
        created_by="user_123",
        updated_by="user_123",
    )
    
    assert promotion.can_apply_to_customer("customer_123") is True
    assert promotion.can_apply_to_customer("customer_789") is False
    assert promotion.can_apply_to_customer(None) is False


def test_increment_usage():
    """Test incrementing promotion usage count."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10"),
    )
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="Test Promotion",
        description="Test",
        discount_rule=rule,
        status=PromotionStatus.ACTIVE,
        start_date=datetime.utcnow(),
        usage_count=5,
        created_by="user_123",
        updated_by="user_123",
    )
    
    initial_version = promotion.version
    promotion.increment_usage()
    
    assert promotion.usage_count == 6
    assert promotion.version == initial_version + 1


def test_activate_promotion():
    """Test activating promotion."""
    rule = DiscountRule(
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10"),
    )
    
    promotion = Promotion(
        id="01JCTEST000000000000000001",
        name="Test Promotion",
        description="Test",
        discount_rule=rule,
        status=PromotionStatus.DRAFT,
        start_date=datetime.utcnow(),
        created_by="user_123",
        updated_by="user_123",
    )
    
    promotion.activate()
    
    assert promotion.status == PromotionStatus.ACTIVE
