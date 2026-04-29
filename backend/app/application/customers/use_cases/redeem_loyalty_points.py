"""Use case for redeeming loyalty points."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.application.customers.loyalty_ports import (
    LoyaltyAccountRepository,
    LoyaltyTransactionRepository,
)
from app.domain.common.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class RedeemPointsResult:
    """Result of redeeming points."""

    transaction_id: str
    points_redeemed: int
    discount_value: Decimal
    new_balance: int


class RedeemLoyaltyPointsUseCase:
    """Redeem loyalty points for a discount."""

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
        points: int,
        reference_id: str | None = None,
        description: str = "",
    ) -> RedeemPointsResult:
        """Redeem points for a discount.

        Args:
            customer_id: The customer's ID
            points: Number of points to redeem
            reference_id: Optional reference (e.g., sale ID)
            description: Optional description

        Returns:
            RedeemPointsResult with transaction details

        Raises:
            NotFoundError: If customer has no loyalty account
            ValidationError: If minimum points not met
            ConflictError: If insufficient points
        """
        # Get loyalty account
        account = await self._account_repo.get_by_customer_id(customer_id)
        if not account:
            raise NotFoundError(
                f"Loyalty account not found for customer {customer_id}",
                code="loyalty.account_not_found",
            )

        old_version = account.version

        # Calculate discount value before redemption
        discount_value = account.calculate_redemption_value(points)

        # Redeem points
        transaction = account.redeem_points(
            points=points,
            reference_id=reference_id,
            description=description,
        )

        # Persist changes
        await self._account_repo.update(account, expected_version=old_version)
        await self._transaction_repo.add(transaction)

        return RedeemPointsResult(
            transaction_id=transaction.id,
            points_redeemed=points,
            discount_value=discount_value,
            new_balance=account.current_points,
        )
