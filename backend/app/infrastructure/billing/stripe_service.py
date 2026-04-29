"""Stripe billing integration for subscription management."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import structlog

from app.core.settings import get_settings
from app.domain.subscriptions.entities import (
    BillingCycle,
    SubscriptionStatus,
    Tenant,
)

logger = structlog.get_logger(__name__)

# Check if Stripe is available
_stripe_available = False
_stripe = None

try:
    import stripe
    _stripe = stripe
    _stripe_available = True
except ImportError:
    pass


@dataclass(frozen=True, slots=True)
class BillingCustomer:
    """Billing customer info."""
    
    id: str
    email: str
    name: str


@dataclass(frozen=True, slots=True)
class BillingSubscription:
    """Billing subscription info."""
    
    id: str
    customer_id: str
    plan_id: str
    status: str
    current_period_end: int  # Unix timestamp
    cancel_at_period_end: bool


class StripeBillingService:
    """Stripe billing integration service.
    
    Handles:
    - Customer creation
    - Subscription management
    - Payment method handling
    - Webhook processing
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = _stripe_available and bool(settings.STRIPE_SECRET_KEY)
        
        if self._enabled and _stripe:
            _stripe.api_key = settings.STRIPE_SECRET_KEY
            logger.info("stripe_billing_enabled")
        else:
            logger.info("stripe_billing_disabled", 
                       stripe_available=_stripe_available,
                       has_key=bool(settings.STRIPE_SECRET_KEY))

    @property
    def enabled(self) -> bool:
        """Check if Stripe billing is enabled."""
        return self._enabled

    async def create_customer(
        self,
        email: str,
        name: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> BillingCustomer | None:
        """Create a Stripe customer.
        
        Args:
            email: Customer email
            name: Customer/business name
            metadata: Additional metadata (e.g., tenant_id)
            
        Returns:
            BillingCustomer or None if disabled
        """
        if not self._enabled or not _stripe:
            logger.debug("stripe_disabled_skip_customer_create")
            return None
        
        try:
            customer = _stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {},
            )
            
            logger.info(
                "stripe_customer_created",
                customer_id=customer.id,
                email=email,
            )
            
            return BillingCustomer(
                id=customer.id,
                email=email,
                name=name,
            )
        except Exception as e:
            logger.error("stripe_customer_create_failed", error=str(e))
            raise

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        *,
        trial_days: int | None = None,
        metadata: dict[str, str] | None = None,
    ) -> BillingSubscription | None:
        """Create a Stripe subscription.
        
        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID for the plan
            trial_days: Optional trial period in days
            metadata: Additional metadata
            
        Returns:
            BillingSubscription or None if disabled
        """
        if not self._enabled or not _stripe:
            logger.debug("stripe_disabled_skip_subscription_create")
            return None
        
        try:
            params: dict[str, Any] = {
                "customer": customer_id,
                "items": [{"price": price_id}],
                "metadata": metadata or {},
            }
            
            if trial_days:
                params["trial_period_days"] = trial_days
            
            subscription = _stripe.Subscription.create(**params)
            
            logger.info(
                "stripe_subscription_created",
                subscription_id=subscription.id,
                customer_id=customer_id,
                status=subscription.status,
            )
            
            return BillingSubscription(
                id=subscription.id,
                customer_id=customer_id,
                plan_id=price_id,
                status=subscription.status,
                current_period_end=subscription.current_period_end,
                cancel_at_period_end=subscription.cancel_at_period_end,
            )
        except Exception as e:
            logger.error("stripe_subscription_create_failed", error=str(e))
            raise

    async def cancel_subscription(
        self,
        subscription_id: str,
        *,
        cancel_immediately: bool = False,
    ) -> bool:
        """Cancel a Stripe subscription.
        
        Args:
            subscription_id: Stripe subscription ID
            cancel_immediately: If True, cancel now. Otherwise, cancel at period end.
            
        Returns:
            True if successful
        """
        if not self._enabled or not _stripe:
            return True
        
        try:
            if cancel_immediately:
                _stripe.Subscription.delete(subscription_id)
            else:
                _stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                )
            
            logger.info(
                "stripe_subscription_cancelled",
                subscription_id=subscription_id,
                immediate=cancel_immediately,
            )
            return True
        except Exception as e:
            logger.error("stripe_subscription_cancel_failed", error=str(e))
            raise

    async def update_subscription_plan(
        self,
        subscription_id: str,
        new_price_id: str,
    ) -> BillingSubscription | None:
        """Update subscription to a new plan.
        
        Args:
            subscription_id: Stripe subscription ID
            new_price_id: New Stripe price ID
            
        Returns:
            Updated BillingSubscription
        """
        if not self._enabled or not _stripe:
            return None
        
        try:
            subscription = _stripe.Subscription.retrieve(subscription_id)
            
            # Update the first item to the new price
            _stripe.Subscription.modify(
                subscription_id,
                items=[{
                    "id": subscription["items"]["data"][0].id,
                    "price": new_price_id,
                }],
                proration_behavior="create_prorations",
            )
            
            # Fetch updated subscription
            updated = _stripe.Subscription.retrieve(subscription_id)
            
            logger.info(
                "stripe_subscription_updated",
                subscription_id=subscription_id,
                new_price_id=new_price_id,
            )
            
            return BillingSubscription(
                id=updated.id,
                customer_id=updated.customer,
                plan_id=new_price_id,
                status=updated.status,
                current_period_end=updated.current_period_end,
                cancel_at_period_end=updated.cancel_at_period_end,
            )
        except Exception as e:
            logger.error("stripe_subscription_update_failed", error=str(e))
            raise

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        *,
        trial_days: int | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str | None:
        """Create a Stripe Checkout session.
        
        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel
            trial_days: Optional trial period
            metadata: Additional metadata
            
        Returns:
            Checkout session URL
        """
        if not self._enabled or not _stripe:
            return None
        
        try:
            params: dict[str, Any] = {
                "customer": customer_id,
                "mode": "subscription",
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata or {},
            }
            
            if trial_days:
                params["subscription_data"] = {
                    "trial_period_days": trial_days,
                }
            
            session = _stripe.checkout.Session.create(**params)
            
            logger.info(
                "stripe_checkout_session_created",
                session_id=session.id,
                customer_id=customer_id,
            )
            
            return session.url
        except Exception as e:
            logger.error("stripe_checkout_create_failed", error=str(e))
            raise

    async def create_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> str | None:
        """Create a Stripe Customer Portal session.
        
        Allows customers to manage their subscription and billing.
        
        Args:
            customer_id: Stripe customer ID
            return_url: URL to return to after portal
            
        Returns:
            Portal session URL
        """
        if not self._enabled or not _stripe:
            return None
        
        try:
            session = _stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            
            logger.info(
                "stripe_portal_session_created",
                customer_id=customer_id,
            )
            
            return session.url
        except Exception as e:
            logger.error("stripe_portal_create_failed", error=str(e))
            raise


def map_stripe_status_to_subscription_status(stripe_status: str) -> SubscriptionStatus:
    """Map Stripe subscription status to our domain status."""
    mapping = {
        "active": SubscriptionStatus.ACTIVE,
        "trialing": SubscriptionStatus.TRIAL,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELLED,
        "unpaid": SubscriptionStatus.PAST_DUE,
        "incomplete": SubscriptionStatus.TRIAL,
        "incomplete_expired": SubscriptionStatus.EXPIRED,
    }
    return mapping.get(stripe_status, SubscriptionStatus.ACTIVE)


# Singleton instance
_billing_service: StripeBillingService | None = None


def get_billing_service() -> StripeBillingService:
    """Get the billing service singleton."""
    global _billing_service
    if _billing_service is None:
        _billing_service = StripeBillingService()
    return _billing_service
