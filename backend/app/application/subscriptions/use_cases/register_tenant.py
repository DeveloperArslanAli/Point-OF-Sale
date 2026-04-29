"""Tenant registration use case."""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.domain.auth.entities import User, UserRole
from app.domain.common.errors import ValidationError, ConflictError
from app.domain.common.identifiers import new_ulid
from app.domain.subscriptions.entities import (
    Tenant,
    SubscriptionStatus,
    BillingCycle,
)


@dataclass(frozen=True, slots=True)
class RegisterTenantCommand:
    """Command to register a new tenant with owner account."""
    
    # Tenant info
    tenant_name: str
    
    # Owner info
    owner_email: str
    owner_password: str
    owner_first_name: str
    owner_last_name: str
    
    # Subscription
    plan_id: str | None = None  # None = free plan
    billing_cycle: str = "monthly"
    
    # Trial
    trial_days: int = 14


@dataclass(frozen=True, slots=True)
class RegisterTenantResult:
    """Result of tenant registration."""
    
    tenant: Tenant
    owner: User
    requires_email_verification: bool = True


class RegisterTenantUseCase:
    """Use case for self-service tenant registration.
    
    Creates a new tenant with:
    1. Unique slug generated from tenant name
    2. Owner user account with admin role
    3. Free trial period
    """

    def __init__(
        self,
        tenant_repository,
        user_repository,
        plan_repository,
        password_hasher,
        *,
        default_trial_days: int = 14,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._user_repo = user_repository
        self._plan_repo = plan_repository
        self._hasher = password_hasher
        self._default_trial_days = default_trial_days

    async def execute(self, command: RegisterTenantCommand) -> RegisterTenantResult:
        """Register a new tenant with owner account."""
        # Validate email format
        if not self._is_valid_email(command.owner_email):
            raise ValidationError(
                f"Invalid email format: {command.owner_email}",
                code="tenant.invalid_email",
            )
        
        # Check if email is already registered
        existing_user = await self._user_repo.get_by_email(command.owner_email)
        if existing_user:
            raise ConflictError(
                "Email already registered",
                code="tenant.email_exists",
            )
        
        # Validate password strength
        self._validate_password(command.owner_password)
        
        # Generate unique slug
        slug = await self._generate_unique_slug(command.tenant_name)
        
        # Get subscription plan (default to free)
        plan_id = command.plan_id
        if not plan_id:
            free_plan = await self._plan_repo.get_by_name("free")
            if free_plan:
                plan_id = free_plan.id
            else:
                # Create a default if none exists
                plan_id = new_ulid()
        
        # Calculate trial end date
        trial_days = command.trial_days or self._default_trial_days
        trial_ends_at = datetime.now(UTC) + timedelta(days=trial_days)
        
        # Create tenant
        tenant = Tenant(
            name=command.tenant_name,
            slug=slug,
            owner_email=command.owner_email,
            subscription_plan_id=plan_id,
            subscription_status=SubscriptionStatus.TRIAL,
            billing_cycle=BillingCycle(command.billing_cycle),
            trial_ends_at=trial_ends_at,
        )
        
        # Hash password
        password_hash = self._hasher(command.owner_password)
        
        # Create owner user
        owner = User(
            email=command.owner_email,
            password_hash=password_hash,
            role=UserRole.ADMIN,
            first_name=command.owner_first_name,
            last_name=command.owner_last_name,
            tenant_id=tenant.id,
            is_active=True,
        )
        
        # Link owner to tenant
        tenant.owner_user_id = owner.id
        
        # Persist
        await self._tenant_repo.add(tenant)
        await self._user_repo.add(owner)
        
        return RegisterTenantResult(
            tenant=tenant,
            owner=owner,
            requires_email_verification=True,
        )

    async def _generate_unique_slug(self, name: str) -> str:
        """Generate a unique URL-safe slug from tenant name."""
        # Convert to lowercase, replace spaces with hyphens
        base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        
        if len(base_slug) < 3:
            base_slug = f"org-{base_slug}"
        
        # Check uniqueness
        slug = base_slug
        counter = 1
        while await self._tenant_repo.get_by_slug(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
            if counter > 100:
                # Add random suffix
                slug = f"{base_slug}-{secrets.token_hex(4)}"
                break
        
        return slug

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def _validate_password(self, password: str) -> None:
        """Validate password meets security requirements."""
        if len(password) < 8:
            raise ValidationError(
                "Password must be at least 8 characters",
                code="tenant.password_too_short",
            )
        
        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                "Password must contain at least one uppercase letter",
                code="tenant.password_no_uppercase",
            )
        
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                "Password must contain at least one lowercase letter",
                code="tenant.password_no_lowercase",
            )
        
        if not re.search(r"\d", password):
            raise ValidationError(
                "Password must contain at least one digit",
                code="tenant.password_no_digit",
            )
