"""Application layer ports for customer loyalty program."""
from __future__ import annotations

from typing import Protocol, Sequence

from app.domain.customers.loyalty import (
    LoyaltyAccount,
    LoyaltyPointTransaction,
)


class LoyaltyAccountRepository(Protocol):
    """Repository protocol for loyalty accounts."""

    async def add(self, account: LoyaltyAccount) -> None:
        """Add a new loyalty account."""
        ...  # pragma: no cover

    async def get_by_id(self, account_id: str) -> LoyaltyAccount | None:
        """Get loyalty account by ID."""
        ...  # pragma: no cover

    async def get_by_customer_id(self, customer_id: str) -> LoyaltyAccount | None:
        """Get loyalty account by customer ID."""
        ...  # pragma: no cover

    async def update(
        self, account: LoyaltyAccount, *, expected_version: int
    ) -> bool:
        """Update loyalty account with optimistic locking."""
        ...  # pragma: no cover

    async def list_by_tier(
        self,
        tier: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[LoyaltyAccount], int]:
        """List loyalty accounts by tier."""
        ...  # pragma: no cover


class LoyaltyTransactionRepository(Protocol):
    """Repository protocol for loyalty point transactions."""

    async def add(self, transaction: LoyaltyPointTransaction) -> None:
        """Add a new point transaction."""
        ...  # pragma: no cover

    async def list_by_account(
        self,
        account_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[LoyaltyPointTransaction], int]:
        """List transactions for an account."""
        ...  # pragma: no cover

    async def list_by_reference(
        self,
        reference_id: str,
    ) -> Sequence[LoyaltyPointTransaction]:
        """List transactions by reference ID (e.g., sale ID)."""
        ...  # pragma: no cover
