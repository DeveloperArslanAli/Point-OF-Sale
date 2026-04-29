from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.db.session import get_session
from app.api.dependencies.auth import get_current_user, require_roles
from app.domain.auth.entities import UserRole, User
from app.infrastructure.db.models.tenant_model import TenantModel
from app.infrastructure.db.models.subscription_plan_model import SubscriptionPlanModel
from app.domain.common.identifiers import new_ulid

router = APIRouter(prefix="/tenants", tags=["Tenants"])

# SUPER_ADMIN only operations
SUPER_ADMIN_ROLE = (UserRole.SUPER_ADMIN,)


class CreateTenantRequest(BaseModel):
    """Request to create a new tenant."""
    name: str = Field(..., min_length=2, max_length=255)
    subscription_plan_id: str
    domain: str | None = None


@router.get("/plans")
async def get_subscription_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """List all subscription plans (any authenticated user)."""
    stmt = select(SubscriptionPlanModel)
    result = await db.execute(stmt)
    plans = result.scalars().all()
    return plans


@router.get("/")
async def get_tenants(
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ROLE))],
    db: AsyncSession = Depends(get_session)
):
    """List all tenants (SUPER_ADMIN only)."""
    stmt = select(TenantModel)
    result = await db.execute(stmt)
    tenants = result.scalars().all()
    return tenants


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: CreateTenantRequest,
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ROLE))],
    db: AsyncSession = Depends(get_session)
):
    """Create a new tenant (SUPER_ADMIN only)."""
    # Check if plan exists
    plan = await db.get(SubscriptionPlanModel, request.subscription_plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    tenant = TenantModel(
        id=new_ulid(),
        name=request.name,
        slug=request.name.lower().replace(" ", "-"),
        domain=request.domain,
        subscription_plan_id=request.subscription_plan_id
    )
    db.add(tenant)
    try:
        await db.commit()
        await db.refresh(tenant)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    return tenant
