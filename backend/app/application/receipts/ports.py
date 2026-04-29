"""Receipt repository port."""

from abc import ABC, abstractmethod
from typing import Optional

from app.domain.receipts import Receipt


class IReceiptRepository(ABC):
    """Receipt repository interface."""

    @abstractmethod
    async def add(self, receipt: Receipt) -> None:
        """Add a new receipt."""
        pass

    @abstractmethod
    async def get_by_id(self, receipt_id: str) -> Optional[Receipt]:
        """Get receipt by ID."""
        pass

    @abstractmethod
    async def get_by_sale_id(self, sale_id: str) -> Optional[Receipt]:
        """Get receipt by sale ID."""
        pass

    @abstractmethod
    async def get_by_receipt_number(self, receipt_number: str) -> Optional[Receipt]:
        """Get receipt by receipt number."""
        pass

    @abstractmethod
    async def list_by_date_range(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Receipt]:
        """List receipts within a date range."""
        pass

    @abstractmethod
    async def update(self, receipt: Receipt) -> None:
        """Update an existing receipt."""
        pass
