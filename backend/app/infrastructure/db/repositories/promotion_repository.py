"""
SQLAlchemy repository for Promotion entities.
"""

from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.promotions.ports import IPromotionRepository
from app.core.tenant import get_current_tenant_id
from app.domain.promotions.entities import (
    DiscountRule,
    DiscountType,
    Promotion,
    PromotionStatus,
    PromotionTarget,
)
from app.infrastructure.db.models.promotion_model import PromotionModel


class PromotionRepository(IPromotionRepository):
    """SQLAlchemy-based promotion repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id and hasattr(PromotionModel, "tenant_id"):
            return stmt.where(PromotionModel.tenant_id == tenant_id)
        return stmt

    async def add(self, promotion: Promotion) -> None:
        """Persist a new promotion."""
        model = self._to_model(promotion)
        model.tenant_id = get_current_tenant_id()
        self._session.add(model)

    async def get_by_id(self, promotion_id: str) -> Optional[Promotion]:
        """Find promotion by ID."""
        stmt = select(PromotionModel).where(PromotionModel.id == promotion_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_coupon_code(self, coupon_code: str) -> Optional[Promotion]:
        """Find promotion by coupon code (case-insensitive)."""
        stmt = select(PromotionModel).where(
            func.upper(PromotionModel.coupon_code) == coupon_code.upper()
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_active(
        self,
        customer_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Promotion]:
        """List active promotions."""
        stmt = (
            select(PromotionModel)
            .where(PromotionModel.status == PromotionStatus.ACTIVE.value)
            .order_by(PromotionModel.priority.desc(), PromotionModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        
        # Apply tenant filter
        stmt = self._apply_tenant_filter(stmt)
        
        # Filter by customer if specified
        if customer_id:
            stmt = stmt.where(
                or_(
                    PromotionModel.customer_ids == [],  # No customer restriction
                    func.json_contains(PromotionModel.customer_ids, f'"{customer_id}"'),
                )
            )
        
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def update(self, promotion: Promotion) -> None:
        """Update an existing promotion."""
        stmt = select(PromotionModel).where(PromotionModel.id == promotion.id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        
        # Update fields from entity
        model.name = promotion.name
        model.description = promotion.description
        model.status = promotion.status.value
        model.discount_rule = self._discount_rule_to_dict(promotion.discount_rule)
        model.end_date = promotion.end_date
        model.usage_limit = promotion.usage_limit
        model.usage_count = promotion.usage_count
        model.usage_limit_per_customer = promotion.usage_limit_per_customer
        model.customer_ids = promotion.customer_ids
        model.exclude_sale_items = promotion.exclude_sale_items
        model.can_combine_with_other_promotions = promotion.can_combine_with_other_promotions
        model.priority = promotion.priority
        model.updated_at = promotion.updated_at
        model.updated_by = promotion.updated_by
        model.version = promotion.version

    async def delete(self, promotion_id: str) -> None:
        """Delete a promotion."""
        stmt = select(PromotionModel).where(PromotionModel.id == promotion_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        await self._session.delete(model)

    async def get_customer_usage_count(
        self,
        promotion_id: str,
        customer_id: str,
    ) -> int:
        """
        Get customer usage count.
        
        Note: This would require a sale_promotions junction table
        to track actual usage. For now, returns 0.
        TODO: Implement in Phase 12.4 when integrating with sales.
        """
        # TODO: Query sale_promotions table
        return 0

    @staticmethod
    def _discount_rule_to_dict(rule: DiscountRule) -> dict:
        """Convert DiscountRule to dict for JSON storage."""
        return {
            "discount_type": rule.discount_type.value,
            "value": str(rule.value),
            "buy_quantity": rule.buy_quantity,
            "get_quantity": rule.get_quantity,
            "min_purchase_amount": str(rule.min_purchase_amount) if rule.min_purchase_amount else None,
            "max_discount_amount": str(rule.max_discount_amount) if rule.max_discount_amount else None,
            "target": rule.target.value,
            "target_product_ids": rule.target_product_ids,
            "target_category_ids": rule.target_category_ids,
        }

    @staticmethod
    def _dict_to_discount_rule(data: dict) -> DiscountRule:
        """Convert dict to DiscountRule entity."""
        from decimal import Decimal
        
        return DiscountRule(
            discount_type=DiscountType(data["discount_type"]),
            value=Decimal(data["value"]),
            buy_quantity=data.get("buy_quantity", 0),
            get_quantity=data.get("get_quantity", 0),
            min_purchase_amount=Decimal(data["min_purchase_amount"]) if data.get("min_purchase_amount") else None,
            max_discount_amount=Decimal(data["max_discount_amount"]) if data.get("max_discount_amount") else None,
            target=PromotionTarget(data.get("target", "order")),
            target_product_ids=data.get("target_product_ids", []),
            target_category_ids=data.get("target_category_ids", []),
        )

    @staticmethod
    def _to_model(entity: Promotion) -> PromotionModel:
        """Convert Promotion entity to ORM model."""
        return PromotionModel(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            status=entity.status.value,
            discount_rule=PromotionRepository._discount_rule_to_dict(entity.discount_rule),
            start_date=entity.start_date,
            end_date=entity.end_date,
            usage_limit=entity.usage_limit,
            usage_count=entity.usage_count,
            usage_limit_per_customer=entity.usage_limit_per_customer,
            coupon_code=entity.coupon_code,
            is_case_sensitive=entity.is_case_sensitive,
            customer_ids=entity.customer_ids,
            exclude_sale_items=entity.exclude_sale_items,
            can_combine_with_other_promotions=entity.can_combine_with_other_promotions,
            priority=entity.priority,
            created_at=entity.created_at,
            created_by=entity.created_by,
            updated_at=entity.updated_at,
            updated_by=entity.updated_by,
            version=entity.version,
        )

    @staticmethod
    def _to_entity(model: PromotionModel) -> Promotion:
        """Convert ORM model to Promotion entity."""
        return Promotion(
            id=model.id,
            name=model.name,
            description=model.description,
            discount_rule=PromotionRepository._dict_to_discount_rule(model.discount_rule),
            status=PromotionStatus(model.status),
            start_date=model.start_date,
            end_date=model.end_date,
            usage_limit=model.usage_limit,
            usage_count=model.usage_count,
            usage_limit_per_customer=model.usage_limit_per_customer,
            coupon_code=model.coupon_code,
            is_case_sensitive=model.is_case_sensitive,
            customer_ids=model.customer_ids or [],
            exclude_sale_items=model.exclude_sale_items,
            can_combine_with_other_promotions=model.can_combine_with_other_promotions,
            priority=model.priority,
            created_at=model.created_at,
            created_by=model.created_by,
            updated_at=model.updated_at,
            updated_by=model.updated_by,
            version=model.version,
        )
