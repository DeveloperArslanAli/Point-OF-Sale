"""
Payment API router.

Handles payment processing endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import SALES_ROLES, require_roles
from app.api.schemas.payment import (
    CapturePaymentRequest,
    CardPaymentResponse,
    PaymentListResponse,
    PaymentResponse,
    ProcessCardPaymentRequest,
    ProcessCashPaymentRequest,
    RefundPaymentRequest,
)
from app.application.payments.use_cases import (
    CapturePayment,
    CapturePaymentCommand,
    GetPaymentsBySale,
    ProcessCardPayment,
    ProcessCardPaymentCommand,
    ProcessCashPayment,
    ProcessCashPaymentCommand,
    RefundPayment,
    RefundPaymentCommand,
)
from app.core.settings import Settings, get_settings
from app.domain.auth.entities import User
from app.infrastructure.db.repositories.payment_repository import PaymentRepository
from app.infrastructure.db.session import get_session
from app.infrastructure.payments.stripe_provider import StripePaymentProvider

router = APIRouter(prefix="/payments", tags=["payments"])


def _payment_to_response(payment) -> PaymentResponse:
    """Map Payment domain entity to response schema."""
    return PaymentResponse(
        id=payment.id,
        sale_id=payment.sale_id,
        method=payment.method.value,
        amount=payment.amount.amount,
        currency=payment.amount.currency,
        status=payment.status.value,
        provider=payment.provider.value,
        provider_transaction_id=payment.provider_transaction_id,
        card_last4=payment.card_last4,
        card_brand=payment.card_brand,
        authorized_at=payment.authorized_at,
        captured_at=payment.captured_at,
        refunded_amount=payment.refunded_amount.amount,
        refunded_at=payment.refunded_at,
        created_at=payment.created_at,
        created_by=payment.created_by,
        notes=payment.notes,
    )


def get_stripe_provider(settings: Annotated[Settings, Depends(get_settings)]) -> StripePaymentProvider:
    """Get Stripe payment provider dependency."""
    return StripePaymentProvider(settings)


@router.post("/cash", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def process_cash_payment(
    payload: ProcessCashPaymentRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
) -> PaymentResponse:
    """
    Process a cash payment.

    Cash payments are completed immediately without provider authorization.
    """
    payment_repo = PaymentRepository(session)
    use_case = ProcessCashPayment(payment_repo)
    
    command = ProcessCashPaymentCommand(
        sale_id=payload.sale_id,
        amount=payload.amount,
        currency=payload.currency,
        user_id=current_user.id,
    )
    
    payment = await use_case.execute(command)
    await session.commit()
    
    return _payment_to_response(payment)


@router.post("/card", response_model=CardPaymentResponse, status_code=status.HTTP_201_CREATED)
async def process_card_payment(
    payload: ProcessCardPaymentRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    stripe_provider: Annotated[StripePaymentProvider, Depends(get_stripe_provider)],
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
) -> CardPaymentResponse:
    """
    Initiate a card payment with Stripe.

    Returns a client_secret that frontend uses to confirm payment.
    """
    payment_repo = PaymentRepository(session)
    use_case = ProcessCardPayment(payment_repo, stripe_provider)
    
    command = ProcessCardPaymentCommand(
        sale_id=payload.sale_id,
        amount=payload.amount,
        currency=payload.currency,
        provider=payload.provider,
        user_id=current_user.id,
        description=payload.description,
        customer_id=payload.customer_id,
    )
    
    payment, client_secret = await use_case.execute(command)
    await session.commit()
    
    response_dict = _payment_to_response(payment).model_dump()
    response_dict["client_secret"] = client_secret
    
    return CardPaymentResponse(**response_dict)


@router.post("/capture", response_model=PaymentResponse)
async def capture_payment(
    payload: CapturePaymentRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    stripe_provider: Annotated[StripePaymentProvider, Depends(get_stripe_provider)],
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
) -> PaymentResponse:
    """
    Capture an authorized payment.

    Moves funds from customer to merchant account.
    """
    payment_repo = PaymentRepository(session)
    use_case = CapturePayment(payment_repo, stripe_provider)
    
    command = CapturePaymentCommand(
        payment_id=payload.payment_id,
        amount=payload.amount,
    )
    
    payment = await use_case.execute(command)
    await session.commit()
    
    return _payment_to_response(payment)


@router.post("/refund", response_model=PaymentResponse)
async def refund_payment(
    payload: RefundPaymentRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    stripe_provider: Annotated[StripePaymentProvider, Depends(get_stripe_provider)],
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
) -> PaymentResponse:
    """
    Refund a completed payment (full or partial).

    For Stripe payments, initiates refund with provider.
    For cash payments, records refund locally.
    """
    payment_repo = PaymentRepository(session)
    use_case = RefundPayment(payment_repo, stripe_provider)
    
    command = RefundPaymentCommand(
        payment_id=payload.payment_id,
        amount=payload.amount,
        reason=payload.reason,
    )
    
    payment = await use_case.execute(command)
    await session.commit()
    
    return _payment_to_response(payment)


@router.get("/sale/{sale_id}", response_model=PaymentListResponse)
async def get_payments_by_sale(
    sale_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
) -> PaymentListResponse:
    """
    Get all payments for a sale.

    Returns payment history including refunds.
    """
    payment_repo = PaymentRepository(session)
    use_case = GetPaymentsBySale(payment_repo)
    
    payments = await use_case.execute(sale_id)
    
    return PaymentListResponse(
        items=[_payment_to_response(p) for p in payments],
        total=len(payments),
    )
