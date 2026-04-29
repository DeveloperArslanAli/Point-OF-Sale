"""
Stripe payment provider implementation.

Integrates with Stripe API for card payment processing.
"""

import logging
from decimal import Decimal
from typing import Optional

import stripe

from app.application.payments.ports import (
    IPaymentProvider,
    PaymentIntentRequest,
    PaymentIntentResult,
    RefundRequest,
    RefundResult,
)
from app.core.settings import Settings
from app.domain.common.errors import DomainError
from app.domain.common.money import Money

logger = logging.getLogger(__name__)


class StripePaymentError(DomainError):
    """Stripe-specific payment error."""

    pass


class StripePaymentProvider(IPaymentProvider):
    """
    Stripe payment provider implementation.

    Handles payment intent creation, capture, refunds via Stripe API.
    """

    def __init__(self, settings: Settings):
        """
        Initialize Stripe provider.

        Args:
            settings: Application settings with Stripe API keys
        """
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("STRIPE_SECRET_KEY is required for Stripe provider")
        
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.currency = settings.PAYMENT_CURRENCY.lower()
        self.publishable_key = settings.STRIPE_PUBLISHABLE_KEY

    async def create_payment_intent(
        self,
        request: PaymentIntentRequest,
    ) -> PaymentIntentResult:
        """
        Create a Stripe PaymentIntent.

        Args:
            request: Payment intent parameters

        Returns:
            PaymentIntentResult with client secret for confirmation
        """
        try:
            # Stripe amounts are in cents (smallest currency unit)
            amount_cents = int(request.amount.amount * 100)
            
            intent_params = {
                "amount": amount_cents,
                "currency": request.amount.currency.lower(),
                "description": request.description,
                "metadata": request.metadata,
                "capture_method": "manual",  # Authorize now, capture later
            }
            
            if request.customer_id:
                intent_params["customer"] = request.customer_id
            
            intent = stripe.PaymentIntent.create(**intent_params)
            
            logger.info(
                "Created Stripe PaymentIntent",
                extra={
                    "intent_id": intent.id,
                    "amount": request.amount.amount,
                    "status": intent.status,
                },
            )
            
            return PaymentIntentResult(
                success=True,
                transaction_id=intent.id,
                client_secret=intent.client_secret,
                requires_action=intent.status == "requires_action",
                metadata={"stripe_status": intent.status},
            )
        
        except stripe.error.CardError as e:
            # Card-specific error (declined, insufficient funds, etc.)
            logger.warning(
                "Stripe card error",
                extra={"error": str(e), "code": e.code},
            )
            return PaymentIntentResult(
                success=False,
                error_message=f"Card error: {e.user_message}",
            )
        
        except stripe.error.StripeError as e:
            # Generic Stripe error
            logger.error(
                "Stripe API error",
                extra={"error": str(e), "type": type(e).__name__},
            )
            return PaymentIntentResult(
                success=False,
                error_message=f"Payment processing error: {str(e)}",
            )
        
        except Exception as e:
            # Unexpected error
            logger.exception("Unexpected error creating PaymentIntent")
            return PaymentIntentResult(
                success=False,
                error_message="An unexpected error occurred",
            )

    async def capture_payment(
        self,
        transaction_id: str,
        amount: Optional[Money] = None,
    ) -> PaymentIntentResult:
        """
        Capture an authorized Stripe PaymentIntent.

        Args:
            transaction_id: Stripe PaymentIntent ID
            amount: Amount to capture (if less than authorized)

        Returns:
            PaymentIntentResult with success status
        """
        try:
            capture_params = {}
            if amount:
                capture_params["amount_to_capture"] = int(amount.amount * 100)
            
            intent = stripe.PaymentIntent.capture(
                transaction_id,
                **capture_params,
            )
            
            logger.info(
                "Captured Stripe PaymentIntent",
                extra={
                    "intent_id": intent.id,
                    "status": intent.status,
                },
            )
            
            return PaymentIntentResult(
                success=True,
                transaction_id=intent.id,
                metadata={"stripe_status": intent.status},
            )
        
        except stripe.error.StripeError as e:
            logger.error(
                "Stripe capture error",
                extra={"error": str(e), "intent_id": transaction_id},
            )
            return PaymentIntentResult(
                success=False,
                error_message=f"Capture failed: {str(e)}",
            )
        
        except Exception as e:
            logger.exception("Unexpected error capturing PaymentIntent")
            return PaymentIntentResult(
                success=False,
                error_message="An unexpected error occurred",
            )

    async def refund_payment(
        self,
        request: RefundRequest,
    ) -> RefundResult:
        """
        Refund a captured Stripe payment.

        Args:
            request: Refund parameters

        Returns:
            RefundResult with refund ID or error
        """
        try:
            amount_cents = int(request.amount.amount * 100)
            
            refund_params = {
                "payment_intent": request.transaction_id,
                "amount": amount_cents,
                "metadata": request.metadata,
            }
            
            if request.reason:
                # Stripe supports: duplicate, fraudulent, requested_by_customer
                refund_params["reason"] = "requested_by_customer"
                refund_params["metadata"]["refund_reason"] = request.reason
            
            refund = stripe.Refund.create(**refund_params)
            
            logger.info(
                "Created Stripe refund",
                extra={
                    "refund_id": refund.id,
                    "amount": request.amount.amount,
                    "status": refund.status,
                },
            )
            
            return RefundResult(
                success=True,
                refund_id=refund.id,
                metadata={"stripe_status": refund.status},
            )
        
        except stripe.error.StripeError as e:
            logger.error(
                "Stripe refund error",
                extra={"error": str(e), "intent_id": request.transaction_id},
            )
            return RefundResult(
                success=False,
                error_message=f"Refund failed: {str(e)}",
            )
        
        except Exception as e:
            logger.exception("Unexpected error creating refund")
            return RefundResult(
                success=False,
                error_message="An unexpected error occurred",
            )

    async def cancel_payment(
        self,
        transaction_id: str,
    ) -> PaymentIntentResult:
        """
        Cancel a Stripe PaymentIntent.

        Args:
            transaction_id: Stripe PaymentIntent ID

        Returns:
            PaymentIntentResult with success status
        """
        try:
            intent = stripe.PaymentIntent.cancel(transaction_id)
            
            logger.info(
                "Cancelled Stripe PaymentIntent",
                extra={
                    "intent_id": intent.id,
                    "status": intent.status,
                },
            )
            
            return PaymentIntentResult(
                success=True,
                transaction_id=intent.id,
                metadata={"stripe_status": intent.status},
            )
        
        except stripe.error.StripeError as e:
            logger.error(
                "Stripe cancel error",
                extra={"error": str(e), "intent_id": transaction_id},
            )
            return PaymentIntentResult(
                success=False,
                error_message=f"Cancellation failed: {str(e)}",
            )
        
        except Exception as e:
            logger.exception("Unexpected error cancelling PaymentIntent")
            return PaymentIntentResult(
                success=False,
                error_message="An unexpected error occurred",
            )

    async def get_payment_status(
        self,
        transaction_id: str,
    ) -> PaymentIntentResult:
        """
        Retrieve Stripe PaymentIntent status.

        Args:
            transaction_id: Stripe PaymentIntent ID

        Returns:
            PaymentIntentResult with current status
        """
        try:
            intent = stripe.PaymentIntent.retrieve(transaction_id)
            
            return PaymentIntentResult(
                success=True,
                transaction_id=intent.id,
                requires_action=intent.status == "requires_action",
                metadata={
                    "stripe_status": intent.status,
                    "amount": Decimal(intent.amount) / 100,
                    "currency": intent.currency,
                },
            )
        
        except stripe.error.StripeError as e:
            logger.error(
                "Stripe status check error",
                extra={"error": str(e), "intent_id": transaction_id},
            )
            return PaymentIntentResult(
                success=False,
                error_message=f"Status check failed: {str(e)}",
            )
        
        except Exception as e:
            logger.exception("Unexpected error retrieving PaymentIntent")
            return PaymentIntentResult(
                success=False,
                error_message="An unexpected error occurred",
            )
