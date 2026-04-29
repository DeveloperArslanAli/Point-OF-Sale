"""Billing API router.

Handles tenant subscription billing via Stripe:
- Create checkout sessions
- Handle Stripe webhooks
- Manage billing portal access
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, require_roles, MANAGEMENT_ROLES
from app.core.settings import get_settings
from app.core.tenant import get_current_tenant_id
from app.domain.auth.entities import User, UserRole
from app.domain.subscriptions.entities import BillingCycle, SubscriptionStatus
from app.infrastructure.billing.stripe_service import (
    StripeBillingService,
    get_billing_service,
    map_stripe_status_to_subscription_status,
)
from app.infrastructure.db.models.tenant_model import TenantModel
from app.infrastructure.db.session import get_session


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

settings = get_settings()


# Request/Response schemas
class CreateCheckoutRequest(BaseModel):
    """Request to create a subscription checkout session."""
    
    plan_id: str = Field(..., description="Subscription plan ID")
    price_id: str = Field(..., description="Stripe price ID for the plan")
    billing_cycle: str = Field(
        "monthly",
        description="Billing cycle: monthly, quarterly, or annual",
    )
    success_url: str = Field(..., description="URL to redirect after successful checkout")
    cancel_url: str = Field(..., description="URL to redirect if checkout is cancelled")
    trial_days: int | None = Field(None, description="Optional trial period in days")


class CheckoutSessionResponse(BaseModel):
    """Response with checkout session URL."""
    
    checkout_url: str
    customer_id: str | None = None


class BillingPortalResponse(BaseModel):
    """Response with billing portal URL."""
    
    portal_url: str


class SubscriptionStatusResponse(BaseModel):
    """Current subscription status."""
    
    plan_id: str | None
    status: str
    billing_cycle: str | None
    stripe_customer_id: str | None
    stripe_subscription_id: str | None


class CancelSubscriptionRequest(BaseModel):
    """Request to cancel subscription."""
    
    immediately: bool = Field(
        False,
        description="Cancel immediately or at end of billing period",
    )


class UpgradeSubscriptionRequest(BaseModel):
    """Request to upgrade/change subscription plan."""
    
    new_price_id: str = Field(..., description="New Stripe price ID to switch to")
    new_plan_id: str = Field(..., description="New plan ID (for internal tracking)")


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CreateCheckoutRequest,
    current_user: Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CheckoutSessionResponse:
    """Create a Stripe checkout session for subscription.
    
    Redirects user to Stripe-hosted checkout page to subscribe.
    """
    billing_service = get_billing_service()
    
    if not billing_service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe billing is not configured",
        )
    
    tenant_id = get_current_tenant_id()
    
    # Get tenant
    stmt = select(TenantModel).where(TenantModel.id == tenant_id)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    
    # Create or get Stripe customer
    customer_id = tenant.stripe_customer_id
    if not customer_id:
        customer = await billing_service.create_customer(
            email=current_user.email,
            name=tenant.name,
            metadata={"tenant_id": tenant_id},
        )
        if customer:
            customer_id = customer.id
            tenant.stripe_customer_id = customer_id
            await session.commit()
    
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing customer",
        )
    
    checkout_url = await billing_service.create_checkout_session(
        customer_id=customer_id,
        price_id=request.price_id,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        trial_days=request.trial_days,
        metadata={
            "tenant_id": tenant_id,
            "plan_id": request.plan_id,
        },
    )
    
    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        )
    
    return CheckoutSessionResponse(
        checkout_url=checkout_url,
        customer_id=customer_id,
    )


@router.get("/portal", response_model=BillingPortalResponse)
async def get_billing_portal(
    return_url: str,
    current_user: Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BillingPortalResponse:
    """Get URL to Stripe Customer Portal for self-service billing management.
    
    Allows customers to update payment methods, view invoices, etc.
    """
    billing_service = get_billing_service()
    
    if not billing_service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe billing is not configured",
        )
    
    tenant_id = get_current_tenant_id()
    
    # Get tenant's Stripe customer ID
    stmt = select(TenantModel).where(TenantModel.id == tenant_id)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()
    
    if not tenant or not tenant.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found. Please subscribe first.",
        )
    
    portal_url = await billing_service.create_portal_session(
        tenant.stripe_customer_id,
        return_url,
    )
    
    if not portal_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing portal session",
        )
    
    return BillingPortalResponse(portal_url=portal_url)


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SubscriptionStatusResponse:
    """Get current subscription status for the tenant."""
    tenant_id = get_current_tenant_id()
    
    stmt = select(TenantModel).where(TenantModel.id == tenant_id)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    
    return SubscriptionStatusResponse(
        plan_id=tenant.subscription_plan_id,
        status=tenant.subscription_status or "active",
        billing_cycle=tenant.billing_cycle,
        stripe_customer_id=tenant.stripe_customer_id,
        stripe_subscription_id=tenant.stripe_subscription_id,
    )


@router.post("/cancel")
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    current_user: Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Cancel the tenant's subscription.
    
    By default, cancels at end of billing period. Set immediately=True to cancel now.
    """
    billing_service = get_billing_service()
    
    if not billing_service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe billing is not configured",
        )
    
    tenant_id = get_current_tenant_id()
    
    stmt = select(TenantModel).where(TenantModel.id == tenant_id)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()
    
    if not tenant or not tenant.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found",
        )
    
    try:
        await billing_service.cancel_subscription(
            tenant.stripe_subscription_id,
            cancel_immediately=request.immediately,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}",
        )
    
    # Update tenant status
    if request.immediately:
        tenant.subscription_status = SubscriptionStatus.CANCELLED.value
    
    await session.commit()
    
    message = "Subscription cancelled" if request.immediately else (
        "Subscription will be cancelled at end of billing period"
    )
    return {"message": message}


@router.post("/upgrade")
async def upgrade_subscription(
    request: UpgradeSubscriptionRequest,
    current_user: Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Upgrade or change the subscription plan."""
    billing_service = get_billing_service()
    
    if not billing_service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe billing is not configured",
        )
    
    tenant_id = get_current_tenant_id()
    
    stmt = select(TenantModel).where(TenantModel.id == tenant_id)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()
    
    if not tenant or not tenant.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found",
        )
    
    try:
        await billing_service.update_subscription_plan(
            tenant.stripe_subscription_id,
            request.new_price_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update subscription: {str(e)}",
        )
    
    # Update tenant plan
    tenant.subscription_plan_id = request.new_plan_id
    await session.commit()
    
    return {"message": f"Subscription updated to plan: {request.new_plan_id}"}


@router.post("/webhook/stripe")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: Annotated[str | None, Header(alias="stripe-signature")] = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Handle Stripe webhook events.
    
    This endpoint is called by Stripe when subscription events occur.
    Verifies the signature and updates tenant status based on event type.
    """
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature",
        )
    
    # Verify webhook signature
    import stripe
    
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )
    
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            webhook_secret,
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook error: {str(e)}",
        )
    
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    
    logger.info(
        "Processing Stripe webhook",
        extra={
            "event_type": event_type,
            "event_id": event.get("id"),
        },
    )
    
    # Handle subscription events
    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        customer_id = data.get("customer")
        subscription_id = data.get("id")
        stripe_status = data.get("status", "")
        
        # Find tenant by Stripe customer ID
        stmt = select(TenantModel).where(
            TenantModel.stripe_customer_id == customer_id
        )
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()
        
        if tenant:
            tenant.stripe_subscription_id = subscription_id
            
            if event_type == "customer.subscription.deleted":
                tenant.subscription_status = SubscriptionStatus.CANCELLED.value
            else:
                domain_status = map_stripe_status_to_subscription_status(stripe_status)
                tenant.subscription_status = domain_status.value
            
            await session.commit()
            
            logger.info(
                "Tenant subscription updated",
                extra={
                    "tenant_id": tenant.id,
                    "event_type": event_type,
                    "new_status": tenant.subscription_status,
                },
            )
    
    # Handle invoice events
    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        
        stmt = select(TenantModel).where(
            TenantModel.stripe_customer_id == customer_id
        )
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()
        
        if tenant:
            tenant.subscription_status = SubscriptionStatus.PAST_DUE.value
            await session.commit()
    
    elif event_type == "invoice.paid":
        customer_id = data.get("customer")
        
        stmt = select(TenantModel).where(
            TenantModel.stripe_customer_id == customer_id
        )
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()
        
        if tenant and tenant.subscription_status == SubscriptionStatus.PAST_DUE.value:
            tenant.subscription_status = SubscriptionStatus.ACTIVE.value
            await session.commit()
    
    # Handle checkout completion
    elif event_type == "checkout.session.completed":
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        metadata = data.get("metadata", {})
        tenant_id = metadata.get("tenant_id")
        plan_id = metadata.get("plan_id")
        
        if tenant_id:
            stmt = select(TenantModel).where(TenantModel.id == tenant_id)
            result = await session.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if tenant:
                tenant.stripe_customer_id = customer_id
                tenant.stripe_subscription_id = subscription_id
                tenant.subscription_status = SubscriptionStatus.ACTIVE.value
                if plan_id:
                    tenant.subscription_plan_id = plan_id
                await session.commit()
    
    return {"status": "processed"}
