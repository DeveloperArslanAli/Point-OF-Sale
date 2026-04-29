"""
Payment processing ports (interfaces).

Defines contracts for payment providers (Stripe, PayPal, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.domain.common.money import Money
from app.domain.payments.entities import Payment, PaymentMethod


@dataclass(slots=True)
class PaymentIntentRequest:
    """Request to create a payment intent with a provider."""

    amount: Money
    payment_method: PaymentMethod
    description: str
    customer_id: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass(slots=True)
class PaymentIntentResult:
    """Result from payment intent creation."""

    success: bool
    transaction_id: Optional[str] = None
    client_secret: Optional[str] = None  # For client-side confirmation
    error_message: Optional[str] = None
    requires_action: bool = False  # 3D Secure, etc.
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass(slots=True)
class RefundRequest:
    """Request to refund a payment."""

    transaction_id: str
    amount: Money
    reason: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass(slots=True)
class RefundResult:
    """Result from refund operation."""

    success: bool
    refund_id: Optional[str] = None
    error_message: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class IPaymentProvider(ABC):
    """
    Payment provider interface.

    Implementations handle provider-specific payment processing logic.
    """

    @abstractmethod
    async def create_payment_intent(
        self,
        request: PaymentIntentRequest,
    ) -> PaymentIntentResult:
        """
        Create a payment intent with the provider.

        Args:
            request: Payment intent parameters

        Returns:
            PaymentIntentResult with transaction ID or error
        """
        pass

    @abstractmethod
    async def capture_payment(
        self,
        transaction_id: str,
        amount: Optional[Money] = None,
    ) -> PaymentIntentResult:
        """
        Capture an authorized payment.

        Args:
            transaction_id: Provider's transaction ID
            amount: Amount to capture (if less than authorized)

        Returns:
            PaymentIntentResult with success status
        """
        pass

    @abstractmethod
    async def refund_payment(
        self,
        request: RefundRequest,
    ) -> RefundResult:
        """
        Refund a captured payment.

        Args:
            request: Refund parameters

        Returns:
            RefundResult with refund ID or error
        """
        pass

    @abstractmethod
    async def cancel_payment(
        self,
        transaction_id: str,
    ) -> PaymentIntentResult:
        """
        Cancel a pending/authorized payment.

        Args:
            transaction_id: Provider's transaction ID

        Returns:
            PaymentIntentResult with success status
        """
        pass

    @abstractmethod
    async def get_payment_status(
        self,
        transaction_id: str,
    ) -> PaymentIntentResult:
        """
        Check payment status with provider.

        Args:
            transaction_id: Provider's transaction ID

        Returns:
            PaymentIntentResult with current status
        """
        pass


class IPaymentRepository(ABC):
    """Payment repository interface."""

    @abstractmethod
    async def add(self, payment: Payment) -> None:
        """
        Persist a new payment.

        Args:
            payment: Payment entity to add
        """
        pass

    @abstractmethod
    async def get_by_id(self, payment_id: str) -> Optional[Payment]:
        """
        Find payment by ID.

        Args:
            payment_id: Payment identifier

        Returns:
            Payment if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_sale_id(self, sale_id: str) -> list[Payment]:
        """
        Find all payments for a sale.

        Args:
            sale_id: Sale identifier

        Returns:
            List of payments for the sale
        """
        pass

    @abstractmethod
    async def update(self, payment: Payment) -> None:
        """
        Update an existing payment.

        Args:
            payment: Payment entity with updates
        """
        pass

    @abstractmethod
    async def get_by_provider_transaction_id(
        self,
        provider_transaction_id: str,
    ) -> Optional[Payment]:
        """
        Find payment by provider transaction ID.

        Args:
            provider_transaction_id: Provider's transaction ID

        Returns:
            Payment if found, None otherwise
        """
        pass
