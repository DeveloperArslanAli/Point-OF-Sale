from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import ceil
from typing import Sequence

from app.application.catalog.ports import ProductRepository
from app.application.inventory.ports import InventoryMovementRepository
from app.domain.catalog.entities import Product
from app.domain.inventory import StockLevel


@dataclass(slots=True)
class InventoryInsightsInput:
    lookback_days: int = 30
    lead_time_days: int = 7
    safety_stock_days: int = 2
    dead_stock_days: int = 90


@dataclass(slots=True)
class LowStockInsight:
    product: Product
    stock: StockLevel
    daily_demand: Decimal
    reorder_point: int
    recommended_order: int
    last_movement_at: datetime | None


@dataclass(slots=True)
class DeadStockInsight:
    product: Product
    stock: StockLevel
    last_movement_at: datetime | None
    days_since_movement: int | None


@dataclass(slots=True)
class InventoryInsightsResult:
    generated_at: datetime
    lookback_days: int
    lead_time_days: int
    safety_stock_days: int
    low_stock: list[LowStockInsight]
    dead_stock: list[DeadStockInsight]


class GetInventoryInsightsUseCase:
    def __init__(
        self,
        product_repo: ProductRepository,
        inventory_repo: InventoryMovementRepository,
    ) -> None:
        self._product_repo = product_repo
        self._inventory_repo = inventory_repo

    async def execute(self, data: InventoryInsightsInput) -> InventoryInsightsResult:
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=data.lookback_days)

        products = await self._collect_products()

        low_stock: list[LowStockInsight] = []
        dead_stock: list[DeadStockInsight] = []

        for product in products:
            stock = await self._inventory_repo.get_stock_level(product.id)
            last_move_at = await self._inventory_repo.get_last_movement_at(product.id)

            outflow_qty = await self._inventory_repo.get_outflow_since(product.id, lookback_start)
            daily_demand = Decimal(outflow_qty) / Decimal(max(1, data.lookback_days))
            reorder_point_value = daily_demand * Decimal(data.lead_time_days + data.safety_stock_days)
            reorder_point_units = ceil(reorder_point_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            recommended_order = max(0, reorder_point_units - stock.quantity_on_hand)

            if stock.quantity_on_hand <= reorder_point_units and reorder_point_units > 0:
                low_stock.append(
                    LowStockInsight(
                        product=product,
                        stock=stock,
                        daily_demand=daily_demand,
                        reorder_point=reorder_point_units,
                        recommended_order=recommended_order,
                        last_movement_at=last_move_at,
                    )
                )

            days_since_movement: int | None = None
            if last_move_at is None:
                days_since_movement = None
            else:
                delta_days = (now - last_move_at.astimezone(UTC)).days
                days_since_movement = delta_days
                if delta_days >= data.dead_stock_days:
                    dead_stock.append(
                        DeadStockInsight(
                            product=product,
                            stock=stock,
                            last_movement_at=last_move_at,
                            days_since_movement=delta_days,
                        )
                    )

            if last_move_at is None and data.dead_stock_days <= 0:
                dead_stock.append(
                    DeadStockInsight(
                        product=product,
                        stock=stock,
                        last_movement_at=None,
                        days_since_movement=None,
                    )
                )

        return InventoryInsightsResult(
            generated_at=now,
            lookback_days=data.lookback_days,
            lead_time_days=data.lead_time_days,
            safety_stock_days=data.safety_stock_days,
            low_stock=sorted(low_stock, key=lambda item: item.stock.quantity_on_hand),
            dead_stock=sorted(
                dead_stock,
                key=lambda item: item.days_since_movement or 0,
                reverse=True,
            ),
        )

    async def _collect_products(self) -> Sequence[Product]:
        # Retrieve active products in batches to keep memory reasonable
        products: list[Product] = []
        offset = 0
        limit = 200
        while True:
            batch, total = await self._product_repo.list_products(offset=offset, limit=limit, active=True)
            products.extend(batch)
            offset += limit
            if offset >= total:
                break
        return products
