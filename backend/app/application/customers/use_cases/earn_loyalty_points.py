"""Use case for earning loyalty points from a purchase."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.application.customers.loyalty_ports import (
    LoyaltyAccountRepository,
    LoyaltyTransactionRepository,
)
from app.domain.common.errors import NotFoundError
from app.domain.customers.loyalty import LoyaltyAccount


@dataclass(frozen=True, slots=True)
class EarnPointsResult:
    """Result of earning points."""

    transaction_id: str
    points_earned: int
    new_balance: int
    tier: str
    tier_changed: bool
    points_to_next_tier: int | None


class EarnLoyaltyPointsUseCase:
    """Earn loyalty points from a purchase."""

    def __init__(
        self,
        loyalty_account_repo: LoyaltyAccountRepository,
        loyalty_transaction_repo: LoyaltyTransactionRepository,
    ) -> None:
        self._account_repo = loyalty_account_repo
        self._transaction_repo = loyalty_transaction_repo

    async def execute(
        self,
        customer_id: str,
        amount: Decimal,
        reference_id: str | None = None,
        description: str = "",
    ) -> EarnPointsResult:
        """Earn points from a purchase.

        Args:
            customer_id: The customer's ID
            amount: Purchase amount in dollars
            reference_id: Optional reference (e.g., sale ID)
            description: Optional description

        Returns:
            EarnPointsResult with transaction details

        Raises:
            NotFoundError: If customer has no loyalty account
        """
        # Get loyalty account
        account = await self._account_repo.get_by_customer_id(customer_id)
        if not account:
            raise NotFoundError(
                f"Loyalty account not found for customer {customer_id}",
                code="loyalty.account_not_found",
            )

        old_tier = account.tier
        old_version = account.version

        # Earn points
        transaction = account.earn_points(
            amount=amount,
            reference_id=reference_id,
            description=description,
        )

        # Persist changes
        await self._account_repo.update(account, expected_version=old_version)
        await self._transaction_repo.add(transaction)

        return EarnPointsResult(
            transaction_id=transaction.id,
            points_earned=transaction.points,
            new_balance=account.current_points,
            tier=account.tier.value,
            tier_changed=account.tier != old_tier,
            points_to_next_tier=account.points_needed_for_next_tier(),
        )
