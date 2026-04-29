"""Payment infrastructure package."""

from app.infrastructure.payments.stripe_provider import StripePaymentProvider

__all__ = ["StripePaymentProvider"]
