"""Super Admin operations router.

Provides system-wide administrative operations for SUPER_ADMIN users only.
These operations affect all tenants and the entire system.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, text

from app.api.dependencies.auth import require_roles
from app.domain.auth.entities import User, UserRole
from app.infrastructure.db.session import get_session
from app.infrastructure.db.models.tenant_model import TenantModel
from app.infrastructure.db.models.auth.user_model import UserModel
from app.infrastructure.db.models.subscription_plan_model import SubscriptionPlanModel
from app.core.pci_compliance import get_compliance_report

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])

# Only SUPER_ADMIN can access these endpoints
SUPER_ADMIN_ONLY = (UserRole.SUPER_ADMIN,)


# ==================== Response Models ====================


class SystemStatsResponse(BaseModel):
    """System-wide statistics."""
    total_tenants: int
    active_tenants: int
    total_users: int
    active_users: int
    total_sales_all_time: int
    total_revenue_all_time: float
    generated_at: datetime


class TenantOverviewResponse(BaseModel):
    """Overview of a single tenant."""
    id: str
    name: str
    slug: str
    is_active: bool
    subscription_plan: str | None
    user_count: int
    created_at: datetime
    trial_ends_at: datetime | None


class TenantListResponse(BaseModel):
    """Paginated list of tenants."""
    items: list[TenantOverviewResponse]
    total: int
    page: int
    page_size: int


class ComplianceCheckResponse(BaseModel):
    """PCI-DSS compliance check results."""
    is_compliant: bool
    critical_issues: list[str]
    warnings: list[str]
    passed_checks: list[str]
    checked_at: datetime


class MaintenanceModeRequest(BaseModel):
    """Request to enable/disable maintenance mode."""
    enabled: bool
    message: str = Field(default="System is under maintenance. Please try again later.")
    allowed_ips: list[str] = Field(default_factory=list)


class TenantActionRequest(BaseModel):
    """Request for tenant actions."""
    tenant_id: str
    reason: str = Field(min_length=10, max_length=500)


class SubscriptionPlanCreate(BaseModel):
    """Create a new subscription plan."""
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None
    price_monthly: float = Field(ge=0)  # Will be stored as price
    duration_months: int = Field(default=1, ge=1)


# ==================== Endpoints ====================


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
    db: AsyncSession = Depends(get_session),
) -> SystemStatsResponse:
    """Get system-wide statistics across all tenants.
    
    Returns aggregate counts and totals for the entire system.
    """
    # Count tenants
    total_tenants = await db.scalar(select(func.count()).select_from(TenantModel))
    active_tenants = await db.scalar(
        select(func.count()).select_from(TenantModel).where(TenantModel.is_active == True)
    )
    
    # Count users
    total_users = await db.scalar(select(func.count()).select_from(UserModel))
    active_users = await db.scalar(
        select(func.count()).select_from(UserModel).where(UserModel.active == True)
    )
    
    # Sales stats - use raw SQL to avoid ORM relationship resolution issues
    sales_result = await db.execute(
        text("SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM sales")
    )
    row = sales_result.fetchone()
    total_sales = row[0] if row else 0
    total_revenue = float(row[1]) if row else 0.0
    
    return SystemStatsResponse(
        total_tenants=total_tenants or 0,
        active_tenants=active_tenants or 0,
        total_users=total_users or 0,
        active_users=active_users or 0,
        total_sales_all_time=total_sales,
        total_revenue_all_time=total_revenue,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/tenants", response_model=TenantListResponse)
async def list_all_tenants(
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
    db: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    active_only: bool = False,
) -> TenantListResponse:
    """List all tenants with their statistics.
    
    Provides an overview of each tenant including user counts.
    """
    # Base query
    query = select(TenantModel)
    count_query = select(func.count()).select_from(TenantModel)
    
    if active_only:
        query = query.where(TenantModel.is_active == True)
        count_query = count_query.where(TenantModel.is_active == True)
    
    # Get total count
    total = await db.scalar(count_query) or 0
    
    # Get tenants with pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(TenantModel.created_at.desc())
    result = await db.execute(query)
    tenants = result.scalars().all()
    
    # Build response with user counts
    items = []
    for tenant in tenants:
        user_count = await db.scalar(
            select(func.count()).select_from(UserModel).where(UserModel.tenant_id == tenant.id)
        ) or 0
        
        # Get plan name
        plan_name = None
        if tenant.subscription_plan_id:
            plan = await db.get(SubscriptionPlanModel, tenant.subscription_plan_id)
            if plan:
                plan_name = plan.name
        
        items.append(TenantOverviewResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            is_active=tenant.is_active,
            subscription_plan=plan_name,
            user_count=user_count,
            created_at=tenant.created_at,
            trial_ends_at=tenant.trial_ends_at,
        ))
    
    return TenantListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/tenants/{tenant_id}/suspend", status_code=status.HTTP_200_OK)
async def suspend_tenant(
    tenant_id: str,
    request: TenantActionRequest,
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Suspend a tenant (disable all access).
    
    This will:
    - Set tenant.is_active = False
    - All users of this tenant will be unable to log in
    """
    tenant = await db.get(TenantModel, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    tenant.is_active = False
    await db.commit()
    
    return {
        "success": True,
        "message": f"Tenant '{tenant.name}' has been suspended",
        "reason": request.reason,
    }


@router.post("/tenants/{tenant_id}/reactivate", status_code=status.HTTP_200_OK)
async def reactivate_tenant(
    tenant_id: str,
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Reactivate a suspended tenant."""
    tenant = await db.get(TenantModel, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    tenant.is_active = True
    await db.commit()
    
    return {
        "success": True,
        "message": f"Tenant '{tenant.name}' has been reactivated",
    }


@router.get("/compliance", response_model=ComplianceCheckResponse)
async def check_pci_compliance(
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
) -> ComplianceCheckResponse:
    """Run PCI-DSS compliance check on the system.
    
    Returns a report of compliance status with any issues found.
    """
    report = get_compliance_report()
    
    critical_issues = []
    warnings = []
    passed_checks = []
    
    for check in report.checks:
        if not check.passed:
            if check.severity == "critical":
                critical_issues.append(f"{check.requirement}: {check.description}")
            else:
                warnings.append(f"{check.requirement}: {check.description}")
        else:
            passed_checks.append(f"{check.requirement}: {check.description}")
    
    return ComplianceCheckResponse(
        is_compliant=report.is_compliant,
        critical_issues=critical_issues,
        warnings=warnings,
        passed_checks=passed_checks,
        checked_at=report.checked_at,
    )


@router.post("/subscription-plans", status_code=status.HTTP_201_CREATED)
async def create_subscription_plan(
    request: SubscriptionPlanCreate,
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a new subscription plan.
    
    Subscription plans define pricing and limits for tenants.
    """
    from app.domain.common.identifiers import new_ulid
    
    plan = SubscriptionPlanModel(
        id=new_ulid(),
        name=request.name,
        description=request.description,
        price=request.price_monthly,
        duration_months=request.duration_months,
    )
    
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    
    return {
        "id": plan.id,
        "name": plan.name,
        "message": "Subscription plan created successfully",
    }


@router.get("/subscription-plans")
async def list_subscription_plans(
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List all subscription plans."""
    result = await db.execute(select(SubscriptionPlanModel))
    plans = result.scalars().all()
    
    return [
        {
            "id": plan.id,
            "name": plan.name,
            "description": plan.description,
            "price": float(plan.price) if plan.price else 0,
            "duration_months": plan.duration_months,
        }
        for plan in plans
    ]


@router.delete("/subscription-plans/{plan_id}")
async def delete_subscription_plan(
    plan_id: str,
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Delete a subscription plan.
    
    Cannot delete if tenants are using this plan.
    """
    plan = await db.get(SubscriptionPlanModel, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Check if any tenants use this plan
    tenant_count = await db.scalar(
        select(func.count()).select_from(TenantModel)
        .where(TenantModel.subscription_plan_id == plan_id)
    )
    
    if tenant_count and tenant_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete plan. {tenant_count} tenant(s) are using it.",
        )
    
    await db.delete(plan)
    await db.commit()
    
    return {"success": True, "message": f"Plan '{plan.name}' deleted"}


@router.get("/database/health")
async def check_database_health(
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Check database health and statistics."""
    try:
        # Check connection
        await db.execute(text("SELECT 1"))
        
        # Get table counts
        tables = {
            "tenants": await db.scalar(select(func.count()).select_from(TenantModel)),
            "users": await db.scalar(select(func.count()).select_from(UserModel)),
            "sales": await db.scalar(select(func.count()).select_from(SaleModel)),
        }
        
        return {
            "status": "healthy",
            "connected": True,
            "table_counts": tables,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


# ==================== Tenant Branding Management ====================


class TenantBrandingRequest(BaseModel):
    """Request to set/update tenant branding."""
    logo_url: str | None = None
    logo_dark_url: str | None = None
    primary_color: str = Field("#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    secondary_color: str = Field("#8b5cf6", pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: str = Field("#bb86fc", pattern=r"^#[0-9a-fA-F]{6}$")
    company_name: str | None = None
    company_tagline: str | None = None
    company_address: str | None = None
    company_phone: str | None = None
    company_email: str | None = None


class TenantSettingsOverview(BaseModel):
    """Overview of tenant settings for SuperAdmin."""
    id: str
    tenant_id: str
    company_name: str
    logo_url: str | None
    primary_color: str
    currency_code: str
    default_tax_rate: float
    theme_mode: str


@router.get("/tenants/{tenant_id}/settings", response_model=TenantSettingsOverview | None)
async def get_tenant_settings(
    tenant_id: str,
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
    db: AsyncSession = Depends(get_session),
) -> dict | None:
    """Get settings overview for a specific tenant."""
    from app.infrastructure.db.models.tenant_settings_model import TenantSettingsModel
    
    tenant = await db.get(TenantModel, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Get settings
    stmt = select(TenantSettingsModel).where(TenantSettingsModel.tenant_id == tenant_id)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()
    
    if not settings:
        return None
    
    return {
        "id": settings.id,
        "tenant_id": settings.tenant_id,
        "company_name": settings.company_name,
        "logo_url": settings.logo_url,
        "primary_color": settings.primary_color,
        "currency_code": settings.currency_code,
        "default_tax_rate": float(settings.default_tax_rate),
        "theme_mode": settings.theme_mode,
    }


@router.put("/tenants/{tenant_id}/branding")
async def set_tenant_branding(
    tenant_id: str,
    request: TenantBrandingRequest,
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Set initial branding for a tenant (SuperAdmin only).
    
    Use this to assign branding when creating/onboarding a new tenant.
    """
    from app.domain.common.identifiers import new_ulid
    from app.infrastructure.db.models.tenant_settings_model import TenantSettingsModel
    
    tenant = await db.get(TenantModel, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Check if settings exist
    stmt = select(TenantSettingsModel).where(TenantSettingsModel.tenant_id == tenant_id)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()
    
    if settings:
        # Update existing
        settings.logo_url = request.logo_url
        settings.logo_dark_url = request.logo_dark_url
        settings.primary_color = request.primary_color
        settings.secondary_color = request.secondary_color
        settings.accent_color = request.accent_color
        if request.company_name:
            settings.company_name = request.company_name
        if request.company_tagline:
            settings.company_tagline = request.company_tagline
        if request.company_address:
            settings.company_address = request.company_address
        if request.company_phone:
            settings.company_phone = request.company_phone
        if request.company_email:
            settings.company_email = request.company_email
        settings.version += 1
    else:
        # Create new with branding
        settings = TenantSettingsModel(
            id=new_ulid(),
            tenant_id=tenant_id,
            logo_url=request.logo_url,
            logo_dark_url=request.logo_dark_url,
            primary_color=request.primary_color,
            secondary_color=request.secondary_color,
            accent_color=request.accent_color,
            company_name=request.company_name or tenant.name,
            company_tagline=request.company_tagline,
            company_address=request.company_address,
            company_phone=request.company_phone,
            company_email=request.company_email,
        )
        db.add(settings)
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Branding updated for tenant '{tenant.name}'",
        "tenant_id": tenant_id,
    }


@router.post("/tenants/{tenant_id}/settings/reset")
async def reset_tenant_settings(
    tenant_id: str,
    _: Annotated[User, Depends(require_roles(*SUPER_ADMIN_ONLY))],
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Reset tenant settings to defaults (SuperAdmin only)."""
    from app.infrastructure.db.models.tenant_settings_model import TenantSettingsModel
    
    tenant = await db.get(TenantModel, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Delete existing settings
    stmt = select(TenantSettingsModel).where(TenantSettingsModel.tenant_id == tenant_id)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()
    
    if settings:
        await db.delete(settings)
        await db.commit()
        
        return {
            "success": True,
            "message": f"Settings reset to defaults for tenant '{tenant.name}'",
        }
    
    return {
        "success": True,
        "message": "No settings to reset (already at defaults)",
    }
