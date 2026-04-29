"""Gift card repository port."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.gift_cards.entities import GiftCard


class IGiftCardRepository(ABC):
    """Gift card repository interface."""

    @abstractmethod
    async def add(self, gift_card: GiftCard) -> None:
        """Add a new gift card."""
        ...

    @abstractmethod
    async def get_by_id(self, gift_card_id: str) -> GiftCard | None:
        """Get a gift card by ID."""
        ...

    @abstractmethod
    async def get_by_code(self, code: str) -> GiftCard | None:
        """Get a gift card by its redemption code."""
        ...

    @abstractmethod
    async def update(self, gift_card: GiftCard) -> None:
        """Update an existing gift card."""
        ...

    @abstractmethod
    async def list_by_customer(
        self,
        customer_id: str,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[GiftCard], int]:
        """
        List gift cards for a customer.
        
        Returns:
            Tuple of (gift_cards, total_count)
        """
        ...
