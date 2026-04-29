"""Use case for getting loyalty account details."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from app.application.customers.loyalty_ports import (
    LoyaltyAccountRepository,
    LoyaltyTransactionRepository,
)
from app.domain.common.errors import NotFoundError
from app.domain.customers.loyalty import LoyaltyPointTransaction


@dataclass(frozen=True, slots=True)
class LoyaltyAccountDetails:
    """Detailed loyalty account information."""

    account_id: str
    customer_id: str
    current_points: int
    lifetime_points: int
    tier: str
    tier_discount_percentage: str
    tier_point_multiplier: str
    points_to_next_tier: int | None
    next_tier: str | None
    enrolled_at: datetime
    recent_transactions: Sequence[LoyaltyPointTransaction]


class GetLoyaltyAccountUseCase:
    """Get detailed loyalty account information."""

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
        *,
        include_transactions: bool = True,
        transaction_limit: int = 10,
    ) -> LoyaltyAccountDetails:
        """Get loyalty account details.

        Args:
            customer_id: The customer's ID
            include_transactions: Whether to include recent transactions
            transaction_limit: Number of recent transactions to include

        Returns:
            LoyaltyAccountDetails with full account information

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

        # Get recent transactions if requested
        recent_transactions: Sequence[LoyaltyPointTransaction] = []
        if include_transactions:
            transactions, _ = await self._transaction_repo.list_by_account(
                account.id, limit=transaction_limit
            )
            recent_transactions = transactions

        # Determine next tier
        from app.domain.customers.loyalty import LoyaltyTier

        tier_order = [
            LoyaltyTier.BRONZE,
            LoyaltyTier.SILVER,
            LoyaltyTier.GOLD,
            LoyaltyTier.PLATINUM,
        ]
        current_idx = tier_order.index(account.tier)
        next_tier = (
            tier_order[current_idx + 1].value
            if current_idx < len(tier_order) - 1
            else None
        )

        return LoyaltyAccountDetails(
            account_id=account.id,
            customer_id=account.customer_id,
            current_points=account.current_points,
            lifetime_points=account.lifetime_points,
            tier=account.tier.value,
            tier_discount_percentage=str(account.tier.discount_percentage),
            tier_point_multiplier=str(account.tier.point_multiplier),
            points_to_next_tier=account.points_needed_for_next_tier(),
            next_tier=next_tier,
            enrolled_at=account.enrolled_at,
            recent_transactions=recent_transactions,
        )
