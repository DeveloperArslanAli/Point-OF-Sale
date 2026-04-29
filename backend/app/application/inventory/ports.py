from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence

from app.domain.inventory import InventoryMovement, StockLevel


class InventoryMovementRepository(Protocol):
    async def add(self, movement: InventoryMovement) -> None: ...  # pragma: no cover

    async def list_for_product(
        self,
        product_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[Sequence[InventoryMovement], int]: ...  # pragma: no cover

    async def get_stock_level(
        self,
        product_id: str,
        *,
        as_of: datetime | None = None,
    ) -> StockLevel: ...  # pragma: no cover

    async def get_last_movement_at(self, product_id: str) -> datetime | None: ...  # pragma: no cover

    async def get_outflow_since(self, product_id: str, since: datetime) -> int: ...  # pragma: no cover

    async def get_outflows_since(self, since: datetime) -> dict[str, int]: ...  # pragma: no cover
