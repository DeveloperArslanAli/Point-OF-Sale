"""Tenant and subscription domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from app.domain.common.identifiers import new_ulid


class SubscriptionStatus(str, Enum):
    """Status of a subscription."""
    
    ACTIVE = "active"
    TRIAL = "trial"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BillingCycle(str, Enum):
    """Billing cycle options."""
    
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


@dataclass(slots=True)
class SubscriptionPlan:
    """Subscription plan defining pricing and features."""
    
    id: str = field(default_factory=new_ulid)
    name: str = ""
    display_name: str = ""
    description: str = ""
    
    # Pricing
    price_monthly: Decimal = Decimal("0")
    price_annual: Decimal = Decimal("0")
    currency: str = "USD"
    
    # Limits
    max_users: int = 5
    max_products: int = 1000
    max_locations: int = 1
    
    # Features
    features: list[str] = field(default_factory=list)
    
    # Status
    is_active: bool = True
    is_public: bool = True  # Show on pricing page
    
    # Legacy compatibility
    price: Decimal = field(default_factory=lambda: Decimal("0"))
    duration_months: int = 1
    
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0
    
    @classmethod
    def create_free_plan(cls) -> "SubscriptionPlan":
        """Create the default free plan."""
        return cls(
            name="free",
            display_name="Free",
            description="Get started with basic POS features",
            price_monthly=Decimal("0"),
            price_annual=Decimal("0"),
            max_users=2,
            max_products=100,
            max_locations=1,
            features=[
                "basic_pos",
                "inventory_tracking",
                "customer_management",
            ],
        )
    
    @classmethod
    def create_starter_plan(cls) -> "SubscriptionPlan":
        """Create the starter plan."""
        return cls(
            name="starter",
            display_name="Starter",
            description="Perfect for small businesses",
            price_monthly=Decimal("29.99"),
            price_annual=Decimal("299.99"),
            max_users=5,
            max_products=1000,
            max_locations=2,
            features=[
                "basic_pos",
                "inventory_tracking",
                "customer_management",
                "promotions",
                "gift_cards",
                "basic_reports",
            ],
        )
    
    @classmethod
    def create_professional_plan(cls) -> "SubscriptionPlan":
        """Create the professional plan."""
        return cls(
            name="professional",
            display_name="Professional",
            description="For growing businesses",
            price_monthly=Decimal("79.99"),
            price_annual=Decimal("799.99"),
            max_users=20,
            max_products=10000,
            max_locations=5,
            features=[
                "basic_pos",
                "inventory_tracking",
                "customer_management",
                "promotions",
                "gift_cards",
                "advanced_reports",
                "api_access",
                "webhooks",
                "loyalty_program",
                "multi_location",
            ],
        )


@dataclass(slots=True)
class Tenant:
    """Tenant (organization) entity."""
    
    id: str = field(default_factory=new_ulid)
    name: str = ""
    slug: str = ""  # URL-safe identifier
    domain: str | None = None  # Custom domain
    
    # Owner info
    owner_user_id: str = ""
    owner_email: str = ""
    
    # Subscription
    subscription_plan_id: str = ""
    subscription_status: SubscriptionStatus = SubscriptionStatus.TRIAL
    billing_cycle: BillingCycle = BillingCycle.MONTHLY
    
    # Trial
    trial_ends_at: datetime | None = None
    
    # Billing
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    
    # Status
    is_active: bool = True
    
    # Metadata
    settings: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0
    
    def activate(self) -> None:
        """Activate the tenant subscription."""
        self.subscription_status = SubscriptionStatus.ACTIVE
        self.is_active = True
        self.updated_at = datetime.now(UTC)
        self.version += 1
    
    def cancel_subscription(self) -> None:
        """Cancel the tenant subscription."""
        self.subscription_status = SubscriptionStatus.CANCELLED
        self.updated_at = datetime.now(UTC)
        self.version += 1
    
    def mark_past_due(self) -> None:
        """Mark subscription as past due (payment failed)."""
        self.subscription_status = SubscriptionStatus.PAST_DUE
        self.updated_at = datetime.now(UTC)
        self.version += 1
    
    def upgrade_plan(self, new_plan_id: str) -> None:
        """Upgrade to a new plan."""
        self.subscription_plan_id = new_plan_id
        self.updated_at = datetime.now(UTC)
        self.version += 1


@dataclass(slots=True)
class TenantInvitation:
    """Invitation to join a tenant."""
    
    id: str = field(default_factory=new_ulid)
    tenant_id: str = ""
    email: str = ""
    role: str = "user"
    invited_by: str = ""
    
    token: str = ""  # Unique invitation token
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
    
    accepted_at: datetime | None = None
    is_accepted: bool = False
    
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def accept(self) -> None:
        """Mark invitation as accepted."""
        self.is_accepted = True
        self.accepted_at = datetime.now(UTC)
    
    @property
    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        return datetime.now(UTC) > self.expires_at
