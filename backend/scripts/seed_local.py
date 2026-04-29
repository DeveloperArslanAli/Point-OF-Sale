"""Seed local Postgres with plan, tenant, and test users for smoke tests.

Creates:
- Subscription plan: "Basic Dev"
- Tenant: "Local Dev Tenant" bound to the plan
- Users:
  * superadmin@pos.com (SUPER_ADMIN, no tenant)
  * admin@retailpos.com (ADMIN, tenant-bound)
  * cashier@retailpos.com (CASHIER, tenant-bound)

Prints access/refresh tokens for admin and cashier with tenant_id embedded.

Usage (from backend/ with DATABASE_URL pointing to Postgres):
  py -m scripts.seed_local
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.core.settings import get_settings
from app.domain.auth.entities import RefreshToken, User, UserRole
from app.domain.common.identifiers import new_ulid
from app.infrastructure.auth.password_hasher import PasswordHasher
from app.infrastructure.auth.token_provider import TokenProvider
from app.infrastructure.db.models.auth.refresh_token_model import RefreshTokenModel
from app.infrastructure.db.models.auth.user_model import UserModel
from app.infrastructure.db.models.subscription_plan_model import SubscriptionPlanModel
from app.infrastructure.db.models.tenant_model import TenantModel
from app.infrastructure.db.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.db.repositories.user_repository import UserRepository
from app.infrastructure.db.session import AsyncSessionLocal


SUPERADMIN_EMAIL = "superadmin@pos.com"
SUPERADMIN_PASSWORD = "SuperSecretPassword123!"

ADMIN_EMAIL = "admin@retailpos.com"
ADMIN_PASSWORD = "AdminPass123!"

CASHIER_EMAIL = "cashier@retailpos.com"
CASHIER_PASSWORD = "CashierPass123!"

PLAN_NAME = "Basic Dev"
TENANT_NAME = "Local Dev Tenant"


async def get_or_create_plan(session) -> SubscriptionPlanModel:
    result = await session.execute(select(SubscriptionPlanModel).where(SubscriptionPlanModel.name == PLAN_NAME))
    plan = result.scalar_one_or_none()
    if plan:
        return plan
    plan = SubscriptionPlanModel(
        id=new_ulid(),
        name=PLAN_NAME,
        price=Decimal("0.00"),
        duration_months=1,
        description="Dev plan",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(plan)
    await session.flush()
    return plan


async def get_or_create_tenant(session, plan_id: str) -> TenantModel:
    result = await session.execute(select(TenantModel).where(TenantModel.name == TENANT_NAME))
    tenant = result.scalar_one_or_none()
    if tenant:
        return tenant
    tenant = TenantModel(
        id=new_ulid(),
        name=TENANT_NAME,
        slug=TENANT_NAME.lower().replace(" ", "-"),
        domain=None,
        subscription_plan_id=plan_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def get_or_create_user(session, *, email: str, password: str, role: UserRole, tenant_id: str | None) -> UserModel:
    result = await session.execute(select(UserModel).where(UserModel.email == email.lower()))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    hasher = PasswordHasher()
    pwd_hash = hasher.hash(password)
    user = User.create(email=email, password_hash=pwd_hash, role=role, tenant_id=tenant_id)
    repo = UserRepository(session)
    await repo.add(user)
    await session.flush()
    # Fetch persisted model to reuse fields
    result = await session.execute(select(UserModel).where(UserModel.id == user.id))
    return result.scalar_one()


async def issue_tokens(session, user: UserModel, *, tenant_id: str | None) -> tuple[str, str]:
    provider = TokenProvider()
    access = provider.create_access_token(
        subject=user.id,
        extra={"role": user.role, "tenant_id": tenant_id},
    )
    refresh, jti, exp = provider.create_refresh_token_with_id(user.id, tenant_id=tenant_id)
    refresh_entity = RefreshToken.issue(user_id=user.id, expires_at=exp, token_id=jti)
    await RefreshTokenRepository(session).add(refresh_entity)
    await session.flush()
    return access, refresh


async def main() -> None:
    settings = get_settings()
    print(f"Using DATABASE_URL={settings.DATABASE_URL}")
    async with AsyncSessionLocal() as session:
        plan = await get_or_create_plan(session)
        tenant = await get_or_create_tenant(session, plan.id)

        superadmin = await get_or_create_user(
            session,
            email=SUPERADMIN_EMAIL,
            password=SUPERADMIN_PASSWORD,
            role=UserRole.SUPER_ADMIN,
            tenant_id=None,
        )

        admin = await get_or_create_user(
            session,
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            role=UserRole.ADMIN,
            tenant_id=tenant.id,
        )

        cashier = await get_or_create_user(
            session,
            email=CASHIER_EMAIL,
            password=CASHIER_PASSWORD,
            role=UserRole.CASHIER,
            tenant_id=tenant.id,
        )

        admin_access, admin_refresh = await issue_tokens(session, admin, tenant_id=tenant.id)
        cashier_access, cashier_refresh = await issue_tokens(session, cashier, tenant_id=tenant.id)

        await session.commit()

    print("Seed complete. Tokens (tenant-scoped):")
    print(f"tenant_id: {tenant.id}")
    print(f"admin.accessToken={admin_access}")
    print(f"admin.refreshToken={admin_refresh}")
    print(f"cashier.accessToken={cashier_access}")
    print(f"cashier.refreshToken={cashier_refresh}")


if __name__ == "__main__":
    asyncio.run(main())