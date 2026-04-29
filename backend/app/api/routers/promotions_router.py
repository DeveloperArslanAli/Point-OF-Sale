"""
Promotion API router.

Handles promotion and discount management endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import MANAGER_ROLES, SALES_ROLES, require_roles
from app.api.schemas.promotion import (
    ApplyPromotionRequest,
    CreatePromotionRequest,
    DiscountCalculationResponse,
    PromotionListResponse,
    PromotionResponse,
    UpdatePromotionRequest,
    ValidateCouponRequest,
)
from app.application.promotions.use_cases import (
    ActivatePromotion,
    ApplyPromotion,
    ApplyPromotionCommand,
    CreatePromotion,
    CreatePromotionCommand,
    DeactivatePromotion,
    DeletePromotion,
    GetPromotion,
    GetPromotionByCouponCode,
    ListActivePromotions,
    UpdatePromotion,
    UpdatePromotionCommand,
)
from app.domain.auth.entities import User
from app.infrastructure.db.repositories.promotion_repository import PromotionRepository
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/promotions", tags=["promotions"])


def _discount_rule_to_schema(rule):
    """Convert DiscountRule to schema dict."""
    from app.api.schemas.promotion import DiscountRuleSchema
    
    return DiscountRuleSchema(
        discount_type=rule.discount_type.value,
        value=rule.value,
        buy_quantity=rule.buy_quantity,
        get_quantity=rule.get_quantity,
        min_purchase_amount=rule.min_purchase_amount,
        max_discount_amount=rule.max_discount_amount,
        target=rule.target.value,
        target_product_ids=rule.target_product_ids,
        target_category_ids=rule.target_category_ids,
    )


def _promotion_to_response(promotion) -> PromotionResponse:
    """Map Promotion domain object to API schema without relying on __dict__."""
    return PromotionResponse(
        id=promotion.id,
        name=promotion.name,
        description=promotion.description,
        discount_rule=_discount_rule_to_schema(promotion.discount_rule),
        status=promotion.status.value,
        start_date=promotion.start_date,
        end_date=promotion.end_date,
        usage_limit=promotion.usage_limit,
        usage_count=promotion.usage_count,
        usage_limit_per_customer=promotion.usage_limit_per_customer,
        coupon_code=promotion.coupon_code,
        is_case_sensitive=promotion.is_case_sensitive,
        customer_ids=promotion.customer_ids,
        exclude_sale_items=promotion.exclude_sale_items,
        can_combine_with_other_promotions=promotion.can_combine_with_other_promotions,
        priority=promotion.priority,
        created_at=promotion.created_at,
        created_by=promotion.created_by,
    )


@router.post("", response_model=PromotionResponse, status_code=status.HTTP_201_CREATED)
async def create_promotion(
    payload: CreatePromotionRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_roles(*MANAGER_ROLES))],
) -> PromotionResponse:
    """
    Create a new promotion.

    Requires manager role or higher.
    """
    promotion_repo = PromotionRepository(session)
    use_case = CreatePromotion(promotion_repo)
    
    command = CreatePromotionCommand(
        name=payload.name,
        description=payload.description,
        discount_type=payload.discount_type,
        value=payload.value,
        start_date=payload.start_date,
        end_date=payload.end_date,
        buy_quantity=payload.buy_quantity,
        get_quantity=payload.get_quantity,
        min_purchase_amount=payload.min_purchase_amount,
        max_discount_amount=payload.max_discount_amount,
        target=payload.target,
        target_product_ids=payload.target_product_ids,
        target_category_ids=payload.target_category_ids,
        usage_limit=payload.usage_limit,
        usage_limit_per_customer=payload.usage_limit_per_customer,
        coupon_code=payload.coupon_code,
        is_case_sensitive=payload.is_case_sensitive,
        customer_ids=payload.customer_ids,
        exclude_sale_items=payload.exclude_sale_items,
        can_combine=payload.can_combine,
        priority=payload.priority,
        user_id=current_user.id,
    )
    
    promotion = await use_case.execute(command)
    await session.commit()
    
    return _promotion_to_response(promotion)


@router.get("/{promotion_id}", response_model=PromotionResponse)
async def get_promotion(
    promotion_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
) -> PromotionResponse:
    """Get promotion by ID."""
    promotion_repo = PromotionRepository(session)
    use_case = GetPromotion(promotion_repo)
    
    promotion = await use_case.execute(promotion_id)
    
    return _promotion_to_response(promotion)


@router.get("", response_model=PromotionListResponse)
async def list_active_promotions(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
    customer_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PromotionListResponse:
    """
    List active promotions.

    Optionally filter by customer ID.
    """
    promotion_repo = PromotionRepository(session)
    use_case = ListActivePromotions(promotion_repo)
    
    promotions = await use_case.execute(customer_id, limit, offset)
    
    return PromotionListResponse(
        items=[
            _promotion_to_response(p)
            for p in promotions
        ],
        total=len(promotions),
    )


@router.patch("/{promotion_id}", response_model=PromotionResponse)
async def update_promotion(
    promotion_id: str,
    payload: UpdatePromotionRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_roles(*MANAGER_ROLES))],
) -> PromotionResponse:
    """
    Update promotion details.

    Requires manager role or higher.
    """
    promotion_repo = PromotionRepository(session)
    use_case = UpdatePromotion(promotion_repo)
    
    command = UpdatePromotionCommand(
        promotion_id=promotion_id,
        name=payload.name,
        description=payload.description,
        end_date=payload.end_date,
        usage_limit=payload.usage_limit,
        usage_limit_per_customer=payload.usage_limit_per_customer,
        priority=payload.priority,
        user_id=current_user.id,
    )
    
    promotion = await use_case.execute(command)
    await session.commit()
    
    return _promotion_to_response(promotion)


@router.post("/{promotion_id}/activate", response_model=PromotionResponse)
async def activate_promotion(
    promotion_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_roles(*MANAGER_ROLES))],
) -> PromotionResponse:
    """
    Activate a promotion.

    Requires manager role or higher.
    """
    promotion_repo = PromotionRepository(session)
    use_case = ActivatePromotion(promotion_repo)
    
    promotion = await use_case.execute(promotion_id)
    await session.commit()
    
    return _promotion_to_response(promotion)


@router.post("/{promotion_id}/deactivate", response_model=PromotionResponse)
async def deactivate_promotion(
    promotion_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_roles(*MANAGER_ROLES))],
) -> PromotionResponse:
    """
    Deactivate a promotion.

    Requires manager role or higher.
    """
    promotion_repo = PromotionRepository(session)
    use_case = DeactivatePromotion(promotion_repo)
    
    promotion = await use_case.execute(promotion_id)
    await session.commit()
    
    return _promotion_to_response(promotion)


@router.delete("/{promotion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_promotion(
    promotion_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_roles(*MANAGER_ROLES))],
) -> None:
    """
    Delete a promotion.

    Requires manager role or higher.
    """
    promotion_repo = PromotionRepository(session)
    use_case = DeletePromotion(promotion_repo)
    
    await use_case.execute(promotion_id)
    await session.commit()


@router.post("/apply", response_model=DiscountCalculationResponse)
async def apply_promotion(
    payload: ApplyPromotionRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
) -> DiscountCalculationResponse:
    """
    Apply promotion and calculate discount.

    Returns discount amount without persisting.
    """
    promotion_repo = PromotionRepository(session)
    use_case = ApplyPromotion(promotion_repo)
    get_promotion_use_case = GetPromotion(promotion_repo)
    
    command = ApplyPromotionCommand(
        promotion_id=payload.promotion_id,
        subtotal=payload.subtotal,
        currency=payload.currency,
        quantity=payload.quantity,
        customer_id=payload.customer_id,
        coupon_code=payload.coupon_code,
    )
    
    discount = await use_case.execute(command)
    promotion = await get_promotion_use_case.execute(payload.promotion_id)
    
    return DiscountCalculationResponse(
        promotion_id=promotion.id,
        promotion_name=promotion.name,
        discount_amount=discount.amount,
        currency=discount.currency,
        original_amount=payload.subtotal,
        final_amount=payload.subtotal - discount.amount,
    )


@router.post("/validate-coupon", response_model=PromotionResponse)
async def validate_coupon(
    payload: ValidateCouponRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
) -> PromotionResponse:
    """
    Validate a coupon code.

    Returns promotion if code is valid and active.
    """
    promotion_repo = PromotionRepository(session)
    use_case = GetPromotionByCouponCode(promotion_repo)
    
    promotion = await use_case.execute(payload.coupon_code)
    
    # Check if customer can use it
    customer_usage = 0
    if payload.customer_id:
        customer_usage = await promotion_repo.get_customer_usage_count(
            promotion.id,
            payload.customer_id,
        )
    
    if not promotion.is_active():
        from app.domain.common.errors import ValidationError
        raise ValidationError("Promotion is not active")
    
    if not promotion.can_apply_to_customer(payload.customer_id, customer_usage):
        from app.domain.common.errors import ValidationError
        raise ValidationError("Promotion cannot be applied to this customer")
    
    return _promotion_to_response(promotion)
