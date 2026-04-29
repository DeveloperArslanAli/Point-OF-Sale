"""Gift card router."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.api.dependencies.auth import require_roles, SALES_ROLES as AUTH_SALES_ROLES
from app.api.schemas.gift_card import (
    GiftCardActivateRequest,
    GiftCardBalanceOut,
    GiftCardOut,
    GiftCardPurchaseRequest,
    GiftCardRedeemRequest,
)
from app.application.gift_cards.use_cases import (
    ActivateGiftCard,
    CheckGiftCardBalance,
    ListCustomerGiftCards,
    PurchaseGiftCard,
    RedeemGiftCard,
)
from app.domain.common.errors import ValidationError
from app.domain.common.money import Money
from app.infrastructure.db.repositories.gift_card_repository import (
    SqlAlchemyGiftCardRepository,
)

router = APIRouter(prefix="/gift-cards", tags=["gift-cards"])


@router.post(
    "/purchase",
    response_model=GiftCardOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*AUTH_SALES_ROLES))],
)
async def purchase_gift_card(
    request: GiftCardPurchaseRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GiftCardOut:
    """
    Purchase a new gift card.
    
    Creates a gift card in PENDING status. Must be activated before use.
    
    Requires: SALES_ROLES (cashier, manager, admin)
    """
    try:
        # Create use case
        repository = SqlAlchemyGiftCardRepository(session)
        use_case = PurchaseGiftCard(repository)

        # Execute
        amount = Money(request.amount, currency=request.currency)
        gift_card = await use_case.execute(
            amount=amount,
            customer_id=request.customer_id,
            validity_days=request.validity_days,
        )

        # Map to response
        return GiftCardOut(
            id=gift_card.id,
            code=gift_card.code,
            initial_balance=gift_card.initial_balance.amount,
            current_balance=gift_card.current_balance.amount,
            currency=gift_card.currency,
            status=gift_card.status.value,
            issued_date=gift_card.issued_date,
            expiry_date=gift_card.expiry_date,
            customer_id=gift_card.customer_id,
            created_at=gift_card.created_at,
            updated_at=gift_card.updated_at,
            version=gift_card.version,
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/activate",
    response_model=GiftCardOut,
    dependencies=[Depends(require_roles(*AUTH_SALES_ROLES))],
)
async def activate_gift_card(
    request: GiftCardActivateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GiftCardOut:
    """
    Activate a purchased gift card.
    
    Transitions card from PENDING to ACTIVE status, making it usable for redemption.
    
    Requires: SALES_ROLES (cashier, manager, admin)
    """
    try:
        # Create use case
        repository = SqlAlchemyGiftCardRepository(session)
        use_case = ActivateGiftCard(repository)

        # Execute
        gift_card = await use_case.execute(request.code)

        # Map to response
        return GiftCardOut(
            id=gift_card.id,
            code=gift_card.code,
            initial_balance=gift_card.initial_balance.amount,
            current_balance=gift_card.current_balance.amount,
            currency=gift_card.currency,
            status=gift_card.status.value,
            issued_date=gift_card.issued_date,
            expiry_date=gift_card.expiry_date,
            customer_id=gift_card.customer_id,
            created_at=gift_card.created_at,
            updated_at=gift_card.updated_at,
            version=gift_card.version,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/redeem",
    response_model=GiftCardOut,
    dependencies=[Depends(require_roles(*AUTH_SALES_ROLES))],
)
async def redeem_gift_card(
    request: GiftCardRedeemRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GiftCardOut:
    """
    Redeem value from a gift card.
    
    Deducts the specified amount from the card's balance. Card transitions to REDEEMED
    status if balance reaches zero.
    
    Requires: SALES_ROLES (cashier, manager, admin)
    """
    try:
        # Create use case
        repository = SqlAlchemyGiftCardRepository(session)
        use_case = RedeemGiftCard(repository)

        # Execute
        amount = Money(request.amount, currency=request.currency)
        gift_card = await use_case.execute(request.code, amount)

        # Map to response
        return GiftCardOut(
            id=gift_card.id,
            code=gift_card.code,
            initial_balance=gift_card.initial_balance.amount,
            current_balance=gift_card.current_balance.amount,
            currency=gift_card.currency,
            status=gift_card.status.value,
            issued_date=gift_card.issued_date,
            expiry_date=gift_card.expiry_date,
            customer_id=gift_card.customer_id,
            created_at=gift_card.created_at,
            updated_at=gift_card.updated_at,
            version=gift_card.version,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/{code}/balance",
    response_model=GiftCardBalanceOut,
    dependencies=[Depends(require_roles(*AUTH_SALES_ROLES))],
)
async def check_gift_card_balance(
    code: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GiftCardBalanceOut:
    """
    Check gift card balance and usability.
    
    Returns current balance and whether the card is usable (active, not expired, has balance).
    Automatically expires the card if past expiry date.
    
    Requires: SALES_ROLES (cashier, manager, admin)
    """
    try:
        # Create use case
        repository = SqlAlchemyGiftCardRepository(session)
        use_case = CheckGiftCardBalance(repository)

        # Execute
        balance, is_usable = await use_case.execute(code)

        # Get gift card for status and expiry
        gift_card = await repository.get_by_code(code)
        if not gift_card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Gift card with code {code} not found",
            )

        # Map to response
        return GiftCardBalanceOut(
            code=gift_card.code,
            current_balance=balance.amount,
            currency=balance.currency,
            status=gift_card.status.value,
            is_usable=is_usable,
            expiry_date=gift_card.expiry_date,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/customer/{customer_id}",
    response_model=list[GiftCardOut],
    dependencies=[Depends(require_roles(*AUTH_SALES_ROLES))],
)
async def list_customer_gift_cards(
    customer_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = 1,
    limit: int = 20,
) -> list[GiftCardOut]:
    """
    List gift cards for a customer.
    
    Returns paginated list of gift cards owned by the specified customer.
    
    Requires: SALES_ROLES (cashier, manager, admin)
    """
    # Create use case
    repository = SqlAlchemyGiftCardRepository(session)
    use_case = ListCustomerGiftCards(repository)

    # Execute
    gift_cards, _ = await use_case.execute(customer_id, page=page, limit=limit)

    # Map to response
    return [
        GiftCardOut(
            id=gc.id,
            code=gc.code,
            initial_balance=gc.initial_balance.amount,
            current_balance=gc.current_balance.amount,
            currency=gc.currency,
            status=gc.status.value,
            issued_date=gc.issued_date,
            expiry_date=gc.expiry_date,
            customer_id=gc.customer_id,
            created_at=gc.created_at,
            updated_at=gc.updated_at,
            version=gc.version,
        )
        for gc in gift_cards
    ]
