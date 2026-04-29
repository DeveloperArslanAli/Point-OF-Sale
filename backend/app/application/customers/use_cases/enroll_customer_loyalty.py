"""Use case for enrolling a customer in the loyalty program."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.customers.loyalty_ports import LoyaltyAccountRepository
from app.application.customers.ports import CustomerRepository
from app.domain.common.errors import ConflictError, NotFoundError
from app.domain.customers.loyalty import LoyaltyAccount


@dataclass(frozen=True, slots=True)
class EnrollCustomerResult:
    """Result of customer enrollment in loyalty program."""

    account_id: str
    customer_id: str
    current_points: int
    tier: str


class EnrollCustomerInLoyaltyUseCase:
    """Enroll a customer in the loyalty program."""

    def __init__(
        self,
        customer_repo: CustomerRepository,
        loyalty_repo: LoyaltyAccountRepository,
    ) -> None:
        self._customer_repo = customer_repo
        self._loyalty_repo = loyalty_repo

    async def execute(self, customer_id: str) -> EnrollCustomerResult:
        """Enroll customer in loyalty program.

        Args:
            customer_id: The ID of the customer to enroll

        Returns:
            EnrollCustomerResult with account details

        Raises:
            NotFoundError: If customer does not exist
            ConflictError: If customer is already enrolled
        """
        # Verify customer exists
        customer = await self._customer_repo.get_by_id(customer_id)
        if not customer:
            raise NotFoundError(
                f"Customer {customer_id} not found",
                code="customer.not_found",
            )

        # Check if already enrolled
        existing = await self._loyalty_repo.get_by_customer_id(customer_id)
        if existing:
            raise ConflictError(
                f"Customer {customer_id} is already enrolled in loyalty program",
                code="loyalty.already_enrolled",
            )

        # Create loyalty account
        account = LoyaltyAccount.enroll(customer_id=customer_id)
        await self._loyalty_repo.add(account)

        return EnrollCustomerResult(
            account_id=account.id,
            customer_id=account.customer_id,
            current_points=account.current_points,
            tier=account.tier.value,
        )
