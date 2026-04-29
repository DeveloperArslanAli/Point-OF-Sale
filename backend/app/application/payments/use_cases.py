"""
Payment processing use cases.

Handles payment creation, authorization, capture, refund workflows.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.application.payments.ports import (
    IPaymentProvider,
    IPaymentRepository,
    PaymentIntentRequest,
    RefundRequest,
)
from app.domain.common.errors import NotFoundError, ValidationError
from app.domain.common.identifiers import generate_ulid
from app.domain.common.money import Money
from app.domain.payments.entities import Payment, PaymentMethod, PaymentProvider


@dataclass(slots=True)
class ProcessCashPaymentCommand:
    """Command to process a cash payment."""

    sale_id: str
    amount: Decimal
    currency: str
    user_id: str


@dataclass(slots=True)
class ProcessCardPaymentCommand:
    """Command to initiate card payment."""

    sale_id: str
    amount: Decimal
    currency: str
    provider: str  # "stripe", "paypal", etc.
    user_id: str
    description: str
    customer_id: str | None = None


@dataclass(slots=True)
class CapturePaymentCommand:
    """Command to capture an authorized payment."""

    payment_id: str
    amount: Decimal | None = None  # Partial capture


@dataclass(slots=True)
class RefundPaymentCommand:
    """Command to refund a payment."""

    payment_id: str
    amount: Decimal
    reason: str | None = None


class ProcessCashPayment:
    """Use case: Process cash payment (immediate completion)."""

    def __init__(self, payment_repo: IPaymentRepository):
        self._payment_repo = payment_repo

    async def execute(self, command: ProcessCashPaymentCommand) -> Payment:
        """
        Process a cash payment.

        Args:
            command: Payment details

        Returns:
            Completed payment entity
        """
        payment_id = generate_ulid()
        amount = Money(command.amount, command.currency)
        
        payment = Payment.create_cash_payment(
            payment_id=payment_id,
            sale_id=command.sale_id,
            amount=amount,
            created_by=command.user_id,
        )
        
        await self._payment_repo.add(payment)
        return payment


class ProcessCardPayment:
    """Use case: Process card payment with provider."""

    def __init__(
        self,
        payment_repo: IPaymentRepository,
        payment_provider: IPaymentProvider,
    ):
        self._payment_repo = payment_repo
        self._provider = payment_provider

    async def execute(self, command: ProcessCardPaymentCommand) -> tuple[Payment, str | None]:
        """
        Initiate card payment with provider.

        Args:
            command: Payment details

        Returns:
            Tuple of (payment entity, client_secret for frontend)
        """
        payment_id = generate_ulid()
        amount = Money(command.amount, command.currency)
        
        # Create pending payment
        provider_enum = PaymentProvider(command.provider)
        payment = Payment.create_card_payment(
            payment_id=payment_id,
            sale_id=command.sale_id,
            amount=amount,
            provider=provider_enum,
            created_by=command.user_id,
        )
        
        # Create payment intent with provider
        intent_request = PaymentIntentRequest(
            amount=amount,
            payment_method=PaymentMethod.CARD,
            description=command.description,
            customer_id=command.customer_id,
            metadata={"sale_id": command.sale_id, "payment_id": payment_id},
        )
        
        result = await self._provider.create_payment_intent(intent_request)
        
        if not result.success:
            payment.fail(result.error_message)
            await self._payment_repo.add(payment)
            raise ValidationError(f"Payment failed: {result.error_message}")
        
        # Update payment with provider transaction ID
        payment.authorize(
            provider_transaction_id=result.transaction_id,
        )
        payment.provider_metadata = result.metadata
        
        await self._payment_repo.add(payment)
        return payment, result.client_secret


class CapturePayment:
    """Use case: Capture an authorized payment."""

    def __init__(
        self,
        payment_repo: IPaymentRepository,
        payment_provider: IPaymentProvider,
    ):
        self._payment_repo = payment_repo
        self._provider = payment_provider

    async def execute(self, command: CapturePaymentCommand) -> Payment:
        """
        Capture an authorized payment.

        Args:
            command: Capture details

        Returns:
            Updated payment entity
        """
        payment = await self._payment_repo.get_by_id(command.payment_id)
        if not payment:
            raise NotFoundError(f"Payment {command.payment_id} not found")
        
        if not payment.provider_transaction_id:
            raise ValidationError("Cannot capture payment without provider transaction ID")
        
        # Capture with provider
        capture_amount = Money(command.amount, payment.amount.currency) if command.amount else None
        result = await self._provider.capture_payment(
            transaction_id=payment.provider_transaction_id,
            amount=capture_amount,
        )
        
        if not result.success:
            payment.fail(result.error_message)
            await self._payment_repo.update(payment)
            raise ValidationError(f"Capture failed: {result.error_message}")
        
        # Update payment status
        payment.capture()
        payment.complete()
        payment.provider_metadata.update(result.metadata)
        
        await self._payment_repo.update(payment)
        return payment


class RefundPayment:
    """Use case: Refund a completed payment."""

    def __init__(
        self,
        payment_repo: IPaymentRepository,
        payment_provider: IPaymentProvider,
    ):
        self._payment_repo = payment_repo
        self._provider = payment_provider

    async def execute(self, command: RefundPaymentCommand) -> Payment:
        """
        Refund a payment.

        Args:
            command: Refund details

        Returns:
            Updated payment entity
        """
        payment = await self._payment_repo.get_by_id(command.payment_id)
        if not payment:
            raise NotFoundError(f"Payment {command.payment_id} not found")
        
        refund_amount = Money(command.amount, payment.amount.currency)
        
        # For cash payments, skip provider call
        if payment.provider == PaymentProvider.INTERNAL:
            payment.refund(refund_amount, command.reason)
            await self._payment_repo.update(payment)
            return payment
        
        # For provider payments, issue refund
        if not payment.provider_transaction_id:
            raise ValidationError("Cannot refund payment without provider transaction ID")
        
        refund_request = RefundRequest(
            transaction_id=payment.provider_transaction_id,
            amount=refund_amount,
            reason=command.reason,
            metadata={"payment_id": payment.id, "sale_id": payment.sale_id},
        )
        
        result = await self._provider.refund_payment(refund_request)
        
        if not result.success:
            raise ValidationError(f"Refund failed: {result.error_message}")
        
        # Update payment with refund
        payment.refund(refund_amount, command.reason)
        payment.provider_metadata["refund_id"] = result.refund_id
        
        await self._payment_repo.update(payment)
        return payment


class GetPaymentsBySale:
    """Use case: Retrieve all payments for a sale."""

    def __init__(self, payment_repo: IPaymentRepository):
        self._payment_repo = payment_repo

    async def execute(self, sale_id: str) -> list[Payment]:
        """
        Get payments for a sale.

        Args:
            sale_id: Sale identifier

        Returns:
            List of payments
        """
        return await self._payment_repo.get_by_sale_id(sale_id)
