"""
Promotion application ports (interfaces).
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.domain.promotions.entities import Promotion


class IPromotionRepository(ABC):
    """Promotion repository interface."""

    @abstractmethod
    async def add(self, promotion: Promotion) -> None:
        """
        Persist a new promotion.

        Args:
            promotion: Promotion entity to add
        """
        pass

    @abstractmethod
    async def get_by_id(self, promotion_id: str) -> Optional[Promotion]:
        """
        Find promotion by ID.

        Args:
            promotion_id: Promotion identifier

        Returns:
            Promotion if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_coupon_code(self, coupon_code: str) -> Optional[Promotion]:
        """
        Find promotion by coupon code.

        Args:
            coupon_code: Coupon code (case-insensitive search)

        Returns:
            Promotion if found, None otherwise
        """
        pass

    @abstractmethod
    async def list_active(
        self,
        customer_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Promotion]:
        """
        List active promotions.

        Args:
            customer_id: Filter by customer (None for all)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of active promotions
        """
        pass

    @abstractmethod
    async def update(self, promotion: Promotion) -> None:
        """
        Update an existing promotion.

        Args:
            promotion: Promotion entity with updates
        """
        pass

    @abstractmethod
    async def delete(self, promotion_id: str) -> None:
        """
        Delete a promotion.

        Args:
            promotion_id: Promotion identifier
        """
        pass

    @abstractmethod
    async def get_customer_usage_count(
        self,
        promotion_id: str,
        customer_id: str,
    ) -> int:
        """
        Get how many times customer used this promotion.

        Args:
            promotion_id: Promotion identifier
            customer_id: Customer identifier

        Returns:
            Usage count
        """
        pass
