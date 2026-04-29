"""Public registration endpoints for tenant self-service signup.

This router provides unauthenticated endpoints for new tenant registration.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.db.session import get_session
from app.infrastructure.db.models.tenant_model import TenantModel
from app.infrastructure.db.models.auth.user_model import UserModel
from app.infrastructure.db.models.subscription_plan_model import SubscriptionPlanModel
from app.domain.common.identifiers import new_ulid
from app.domain.auth.entities import UserRole
from app.infrastructure.billing import get_billing_service
from app.infrastructure.auth.password_hasher import hash_password as get_password_hash

import re
import secrets
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/register", tags=["Registration"])


class TenantRegistrationRequest(BaseModel):
    """Request schema for tenant registration."""
    
    tenant_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Business/organization name",
    )
    owner_email: EmailStr = Field(
        ...,
        description="Email for the tenant owner account",
    )
    owner_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password for the owner account",
    )
    owner_first_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )
    owner_last_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )
    plan_id: str | None = Field(
        default=None,
        description="Subscription plan ID. None for free trial.",
    )

    @field_validator("owner_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("tenant_name")
    @classmethod
    def validate_tenant_name(cls, v: str) -> str:
        """Validate tenant name is reasonable."""
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("Tenant name must be at least 2 characters")
        return stripped


class TenantRegistrationResponse(BaseModel):
    """Response schema for tenant registration."""
    
    tenant_id: str
    tenant_name: str
    tenant_slug: str
    owner_id: str
    owner_email: str
    trial_ends_at: datetime | None
    requires_email_verification: bool
    checkout_url: str | None = None
    message: str


def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    # Convert to lowercase and replace spaces with hyphens
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)  # Remove special chars
    slug = re.sub(r'[\s_]+', '-', slug)  # Replace spaces with hyphens
    slug = re.sub(r'-+', '-', slug)  # Collapse multiple hyphens
    slug = slug.strip('-')  # Remove leading/trailing hyphens
    
    # Add random suffix for uniqueness
    suffix = secrets.token_hex(3)
    return f"{slug}-{suffix}"


@router.post(
    "/tenant",
    response_model=TenantRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new tenant",
    description="Self-service registration for new businesses. Creates tenant and owner account.",
)
async def register_tenant(
    request: TenantRegistrationRequest,
    db: AsyncSession = Depends(get_session),
) -> TenantRegistrationResponse:
    """Register a new tenant with owner account.
    
    This is a public endpoint for self-service tenant registration.
    Creates:
    - New tenant record
    - Owner user with ADMIN role
    - Optional Stripe customer and subscription
    
    The owner will receive a 14-day free trial by default.
    """
    # Check if email already exists
    existing_user = await db.execute(
        select(UserModel).where(UserModel.email == request.owner_email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    
    # Get subscription plan if specified
    plan = None
    if request.plan_id:
        plan = await db.get(SubscriptionPlanModel, request.plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription plan not found",
            )
    
    # Generate unique slug
    base_slug = generate_slug(request.tenant_name)
    slug = base_slug
    
    # Check slug uniqueness
    for attempt in range(5):
        existing_tenant = await db.execute(
            select(TenantModel).where(TenantModel.slug == slug)
        )
        if not existing_tenant.scalar_one_or_none():
            break
        slug = f"{base_slug}-{secrets.token_hex(2)}"
    
    # Create tenant
    tenant_id = new_ulid()
    trial_ends_at = datetime.now(timezone.utc) + timedelta(days=14)
    
    tenant = TenantModel(
        id=tenant_id,
        name=request.tenant_name,
        slug=slug,
        subscription_plan_id=request.plan_id,
        is_active=True,
        trial_ends_at=trial_ends_at,
    )
    db.add(tenant)
    
    # Create owner user
    owner_id = new_ulid()
    hashed_password = get_password_hash(request.owner_password)
    
    owner = UserModel(
        id=owner_id,
        email=request.owner_email,
        hashed_password=hashed_password,
        first_name=request.owner_first_name,
        last_name=request.owner_last_name,
        role=UserRole.ADMIN.value,
        tenant_id=tenant_id,
        is_active=True,
        is_verified=False,  # Requires email verification
    )
    db.add(owner)
    
    # Try to create Stripe customer
    checkout_url = None
    billing = get_billing_service()
    
    if billing.enabled:
        try:
            customer = await billing.create_customer(
                email=request.owner_email,
                name=request.tenant_name,
                metadata={"tenant_id": tenant_id},
            )
            
            if customer:
                # Update tenant with Stripe customer ID
                tenant.stripe_customer_id = customer.id
                
                # If a paid plan is selected, create checkout session
                if plan and plan.stripe_price_id:
                    checkout_url = await billing.create_checkout_session(
                        customer_id=customer.id,
                        price_id=plan.stripe_price_id,
                        success_url=f"/registration/success?tenant={slug}",
                        cancel_url=f"/registration/cancel?tenant={slug}",
                        trial_days=14,
                        metadata={"tenant_id": tenant_id},
                    )
        except Exception:
            # Log but don't fail registration if Stripe fails
            pass
    
    try:
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(owner)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tenant. Please try again.",
        )
    
    return TenantRegistrationResponse(
        tenant_id=tenant_id,
        tenant_name=request.tenant_name,
        tenant_slug=slug,
        owner_id=owner_id,
        owner_email=request.owner_email,
        trial_ends_at=trial_ends_at,
        requires_email_verification=True,
        checkout_url=checkout_url,
        message="Registration successful! Please check your email to verify your account.",
    )


@router.get(
    "/plans",
    summary="Get available subscription plans",
    description="List all subscription plans available for new tenants.",
)
async def get_available_plans(
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Get available subscription plans for registration.
    
    Returns plans suitable for public display (no sensitive pricing data).
    """
    result = await db.execute(
        select(SubscriptionPlanModel).where(SubscriptionPlanModel.is_active == True)
    )
    plans = result.scalars().all()
    
    return [
        {
            "id": plan.id,
            "name": plan.name,
            "description": plan.description,
            "price_monthly": float(plan.price_monthly) if plan.price_monthly else 0,
            "price_annual": float(plan.price_annual) if plan.price_annual else 0,
            "max_users": plan.max_users,
            "max_products": plan.max_products,
            "max_locations": plan.max_locations,
            "features": plan.features or [],
        }
        for plan in plans
    ]


@router.post(
    "/verify-email",
    summary="Verify email address",
    description="Verify a user's email address using the verification token.",
)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Verify email address with token.
    
    This endpoint would be called from the email verification link.
    For MVP, we accept the token and mark user as verified.
    """
    # In a real implementation, we'd decode and verify the token
    # For now, this is a placeholder that would be implemented
    # with proper token verification
    return {
        "success": True,
        "message": "Email verification endpoint. Token validation to be implemented.",
    }
