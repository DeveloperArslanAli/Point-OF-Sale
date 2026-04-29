"""
Promotion use cases.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.application.promotions.ports import IPromotionRepository
from app.domain.common.errors import NotFoundError, ValidationError
from app.domain.common.identifiers import generate_ulid
from app.domain.common.money import Money
from app.domain.promotions.entities import (
    DiscountRule,
    DiscountType,
    Promotion,
    PromotionStatus,
    PromotionTarget,
)


@dataclass(slots=True)
class CreatePromotionCommand:
    """Command to create a promotion."""

    name: str
    description: str
    discount_type: str
    value: Decimal
    start_date: datetime
    user_id: str
    
    # Optional fields
    end_date: Optional[datetime] = None
    buy_quantity: int = 0
    get_quantity: int = 0
    min_purchase_amount: Optional[Decimal] = None
    max_discount_amount: Optional[Decimal] = None
    target: str = "order"
    target_product_ids: list[str] = None
    target_category_ids: list[str] = None
    usage_limit: Optional[int] = None
    usage_limit_per_customer: Optional[int] = None
    coupon_code: Optional[str] = None
    is_case_sensitive: bool = False
    customer_ids: list[str] = None
    exclude_sale_items: bool = False
    can_combine: bool = False
    priority: int = 0

    def __post_init__(self):
        if self.target_product_ids is None:
            self.target_product_ids = []
        if self.target_category_ids is None:
            self.target_category_ids = []
        if self.customer_ids is None:
            self.customer_ids = []


@dataclass(slots=True)
class UpdatePromotionCommand:
    """Command to update a promotion."""

    promotion_id: str
    user_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    end_date: Optional[datetime] = None
    usage_limit: Optional[int] = None
    usage_limit_per_customer: Optional[int] = None
    priority: Optional[int] = None


@dataclass(slots=True)
class ApplyPromotionCommand:
    """Command to apply promotion to an amount."""

    promotion_id: str
    subtotal: Decimal
    currency: str
    quantity: int = 1
    customer_id: Optional[str] = None
    coupon_code: Optional[str] = None


class CreatePromotion:
    """Use case: Create a new promotion."""

    def __init__(self, promotion_repo: IPromotionRepository):
        self._promotion_repo = promotion_repo

    async def execute(self, command: CreatePromotionCommand) -> Promotion:
        """
        Create a promotion.

        Args:
            command: Promotion details

        Returns:
            Created promotion entity
        """
        # Check for duplicate coupon code
        if command.coupon_code:
            existing = await self._promotion_repo.get_by_coupon_code(command.coupon_code)
            if existing:
                raise ValidationError(f"Coupon code '{command.coupon_code}' already exists")
        
        # Create discount rule
        discount_rule = DiscountRule(
            discount_type=DiscountType(command.discount_type),
            value=command.value,
            buy_quantity=command.buy_quantity,
            get_quantity=command.get_quantity,
            min_purchase_amount=command.min_purchase_amount,
            max_discount_amount=command.max_discount_amount,
            target=PromotionTarget(command.target),
            target_product_ids=command.target_product_ids,
            target_category_ids=command.target_category_ids,
        )
        
        # Create promotion
        promotion = Promotion(
            id=generate_ulid(),
            name=command.name,
            description=command.description,
            discount_rule=discount_rule,
            status=PromotionStatus.DRAFT,
            start_date=command.start_date,
            end_date=command.end_date,
            usage_limit=command.usage_limit,
            usage_limit_per_customer=command.usage_limit_per_customer,
            coupon_code=command.coupon_code,
            is_case_sensitive=command.is_case_sensitive,
            customer_ids=command.customer_ids,
            exclude_sale_items=command.exclude_sale_items,
            can_combine_with_other_promotions=command.can_combine,
            priority=command.priority,
            created_by=command.user_id,
            updated_by=command.user_id,
        )
        
        await self._promotion_repo.add(promotion)
        return promotion


class GetPromotion:
    """Use case: Get promotion by ID."""

    def __init__(self, promotion_repo: IPromotionRepository):
        self._promotion_repo = promotion_repo

    async def execute(self, promotion_id: str) -> Promotion:
        """
        Get promotion by ID.

        Args:
            promotion_id: Promotion identifier

        Returns:
            Promotion entity

        Raises:
            NotFoundError: If promotion not found
        """
        promotion = await self._promotion_repo.get_by_id(promotion_id)
        if not promotion:
            raise NotFoundError(f"Promotion {promotion_id} not found")
        return promotion


class GetPromotionByCouponCode:
    """Use case: Get promotion by coupon code."""

    def __init__(self, promotion_repo: IPromotionRepository):
        self._promotion_repo = promotion_repo

    async def execute(self, coupon_code: str) -> Promotion:
        """
        Get promotion by coupon code.

        Args:
            coupon_code: Coupon code

        Returns:
            Promotion entity

        Raises:
            NotFoundError: If promotion not found
        """
        promotion = await self._promotion_repo.get_by_coupon_code(coupon_code)
        if not promotion:
            raise NotFoundError(f"Promotion with code '{coupon_code}' not found")
        return promotion


class ListActivePromotions:
    """Use case: List active promotions."""

    def __init__(self, promotion_repo: IPromotionRepository):
        self._promotion_repo = promotion_repo

    async def execute(
        self,
        customer_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Promotion]:
        """
        List active promotions.

        Args:
            customer_id: Filter by customer
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of active promotions
        """
        return await self._promotion_repo.list_active(customer_id, limit, offset)


class UpdatePromotion:
    """Use case: Update promotion details."""

    def __init__(self, promotion_repo: IPromotionRepository):
        self._promotion_repo = promotion_repo

    async def execute(self, command: UpdatePromotionCommand) -> Promotion:
        """
        Update promotion.

        Args:
            command: Update details

        Returns:
            Updated promotion entity
        """
        promotion = await self._promotion_repo.get_by_id(command.promotion_id)
        if not promotion:
            raise NotFoundError(f"Promotion {command.promotion_id} not found")
        
        # Update fields
        if command.name:
            promotion.name = command.name
        if command.description:
            promotion.description = command.description
        if command.end_date:
            promotion.end_date = command.end_date
        if command.usage_limit is not None:
            promotion.usage_limit = command.usage_limit
        if command.usage_limit_per_customer is not None:
            promotion.usage_limit_per_customer = command.usage_limit_per_customer
        if command.priority is not None:
            promotion.priority = command.priority
        
        promotion.updated_by = command.user_id
        promotion.updated_at = datetime.utcnow()
        promotion.version += 1
        
        await self._promotion_repo.update(promotion)
        return promotion


class ActivatePromotion:
    """Use case: Activate a promotion."""

    def __init__(self, promotion_repo: IPromotionRepository):
        self._promotion_repo = promotion_repo

    async def execute(self, promotion_id: str) -> Promotion:
        """
        Activate promotion.

        Args:
            promotion_id: Promotion identifier

        Returns:
            Activated promotion entity
        """
        promotion = await self._promotion_repo.get_by_id(promotion_id)
        if not promotion:
            raise NotFoundError(f"Promotion {promotion_id} not found")
        
        promotion.activate()
        await self._promotion_repo.update(promotion)
        return promotion


class DeactivatePromotion:
    """Use case: Deactivate a promotion."""

    def __init__(self, promotion_repo: IPromotionRepository):
        self._promotion_repo = promotion_repo

    async def execute(self, promotion_id: str) -> Promotion:
        """
        Deactivate promotion.

        Args:
            promotion_id: Promotion identifier

        Returns:
            Deactivated promotion entity
        """
        promotion = await self._promotion_repo.get_by_id(promotion_id)
        if not promotion:
            raise NotFoundError(f"Promotion {promotion_id} not found")
        
        promotion.deactivate()
        await self._promotion_repo.update(promotion)
        return promotion


class ApplyPromotion:
    """Use case: Apply promotion to calculate discount."""

    def __init__(self, promotion_repo: IPromotionRepository):
        self._promotion_repo = promotion_repo

    async def execute(self, command: ApplyPromotionCommand) -> Money:
        """
        Apply promotion and calculate discount.

        Args:
            command: Application details

        Returns:
            Discount amount
        """
        promotion = await self._promotion_repo.get_by_id(command.promotion_id)
        if not promotion:
            raise NotFoundError(f"Promotion {command.promotion_id} not found")
        
        # Get customer usage count
        customer_usage = 0
        if command.customer_id:
            customer_usage = await self._promotion_repo.get_customer_usage_count(
                command.promotion_id,
                command.customer_id,
            )
        
        # Apply discount
        subtotal = Money(command.subtotal, command.currency)
        discount = promotion.apply_discount(
            subtotal=subtotal,
            quantity=command.quantity,
            customer_id=command.customer_id,
            customer_usage_count=customer_usage,
            coupon_code=command.coupon_code,
        )
        
        return discount


class DeletePromotion:
    """Use case: Delete a promotion."""

    def __init__(self, promotion_repo: IPromotionRepository):
        self._promotion_repo = promotion_repo

    async def execute(self, promotion_id: str) -> None:
        """
        Delete promotion.

        Args:
            promotion_id: Promotion identifier
        """
        promotion = await self._promotion_repo.get_by_id(promotion_id)
        if not promotion:
            raise NotFoundError(f"Promotion {promotion_id} not found")
        
        await self._promotion_repo.delete(promotion_id)
