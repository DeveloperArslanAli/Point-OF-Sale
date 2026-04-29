"""Loyalty program API router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_roles, SALES_ROLES, MANAGEMENT_ROLES
from app.infrastructure.db.session import get_session
from app.api.schemas.loyalty import (
    LoyaltyAccountOut,
    LoyaltyEarnPointsRequest,
    LoyaltyEarnPointsResponse,
    LoyaltyEnrollRequest,
    LoyaltyEnrollResponse,
    LoyaltyRedeemPointsRequest,
    LoyaltyRedeemPointsResponse,
    LoyaltyTransactionOut,
)
from app.application.customers.use_cases.earn_loyalty_points import EarnLoyaltyPointsUseCase
from app.application.customers.use_cases.enroll_customer_loyalty import EnrollCustomerInLoyaltyUseCase
from app.application.customers.use_cases.get_loyalty_account import GetLoyaltyAccountUseCase
from app.application.customers.use_cases.redeem_loyalty_points import RedeemLoyaltyPointsUseCase
from app.infrastructure.db.repositories.customer_repository import SqlAlchemyCustomerRepository
from app.infrastructure.db.repositories.loyalty_repository import (
    SqlAlchemyLoyaltyAccountRepository,
    SqlAlchemyLoyaltyTransactionRepository,
)

router = APIRouter(prefix="/loyalty", tags=["loyalty"])


@router.post("/enroll", response_model=LoyaltyEnrollResponse)
async def enroll_customer(
    request: LoyaltyEnrollRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*SALES_ROLES))],
) -> LoyaltyEnrollResponse:
    """Enroll a customer in the loyalty program."""
    customer_repo = SqlAlchemyCustomerRepository(session)
    loyalty_repo = SqlAlchemyLoyaltyAccountRepository(session)

    use_case = EnrollCustomerInLoyaltyUseCase(
        customer_repo=customer_repo,
        loyalty_repo=loyalty_repo,
    )

    result = await use_case.execute(request.customer_id)

    return LoyaltyEnrollResponse(
        account_id=result.account_id,
        customer_id=result.customer_id,
        current_points=result.current_points,
        tier=result.tier,
    )


@router.post("/earn", response_model=LoyaltyEarnPointsResponse)
async def earn_points(
    request: LoyaltyEarnPointsRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*SALES_ROLES))],
) -> LoyaltyEarnPointsResponse:
    """Earn loyalty points from a purchase."""
    account_repo = SqlAlchemyLoyaltyAccountRepository(session)
    transaction_repo = SqlAlchemyLoyaltyTransactionRepository(session)

    use_case = EarnLoyaltyPointsUseCase(
        loyalty_account_repo=account_repo,
        loyalty_transaction_repo=transaction_repo,
    )

    result = await use_case.execute(
        customer_id=request.customer_id,
        amount=request.amount,
        reference_id=request.reference_id,
        description=request.description,
    )

    return LoyaltyEarnPointsResponse(
        transaction_id=result.transaction_id,
        points_earned=result.points_earned,
        new_balance=result.new_balance,
        tier=result.tier,
        tier_changed=result.tier_changed,
        points_to_next_tier=result.points_to_next_tier,
    )


@router.post("/redeem", response_model=LoyaltyRedeemPointsResponse)
async def redeem_points(
    request: LoyaltyRedeemPointsRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*SALES_ROLES))],
) -> LoyaltyRedeemPointsResponse:
    """Redeem loyalty points for a discount."""
    account_repo = SqlAlchemyLoyaltyAccountRepository(session)
    transaction_repo = SqlAlchemyLoyaltyTransactionRepository(session)

    use_case = RedeemLoyaltyPointsUseCase(
        loyalty_account_repo=account_repo,
        loyalty_transaction_repo=transaction_repo,
    )

    result = await use_case.execute(
        customer_id=request.customer_id,
        points=request.points,
        reference_id=request.reference_id,
        description=request.description,
    )

    return LoyaltyRedeemPointsResponse(
        transaction_id=result.transaction_id,
        points_redeemed=result.points_redeemed,
        discount_value=str(result.discount_value),
        new_balance=result.new_balance,
    )


@router.get("/account/{customer_id}", response_model=LoyaltyAccountOut)
async def get_loyalty_account(
    customer_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*SALES_ROLES))],
    include_transactions: Annotated[bool, Query()] = True,
    transaction_limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> LoyaltyAccountOut:
    """Get loyalty account details for a customer."""
    account_repo = SqlAlchemyLoyaltyAccountRepository(session)
    transaction_repo = SqlAlchemyLoyaltyTransactionRepository(session)

    use_case = GetLoyaltyAccountUseCase(
        loyalty_account_repo=account_repo,
        loyalty_transaction_repo=transaction_repo,
    )

    result = await use_case.execute(
        customer_id=customer_id,
        include_transactions=include_transactions,
        transaction_limit=transaction_limit,
    )

    return LoyaltyAccountOut(
        account_id=result.account_id,
        customer_id=result.customer_id,
        current_points=result.current_points,
        lifetime_points=result.lifetime_points,
        tier=result.tier,
        tier_discount_percentage=result.tier_discount_percentage,
        tier_point_multiplier=result.tier_point_multiplier,
        points_to_next_tier=result.points_to_next_tier,
        next_tier=result.next_tier,
        enrolled_at=result.enrolled_at,
        recent_transactions=[
            LoyaltyTransactionOut(
                id=t.id,
                transaction_type=t.transaction_type.value,
                points=t.points,
                balance_after=t.balance_after,
                reference_id=t.reference_id,
                description=t.description,
                created_at=t.created_at,
            )
            for t in result.recent_transactions
        ],
    )
