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
class InventoryForecastInput:
    lookback_days: int = 60
    lead_time_days: int = 7
    safety_stock_days: int = 2
    include_zero_demand: bool = False
    ttl_minutes: int = 360


@dataclass(slots=True)
class ForecastInsight:
    product: Product
    stock: StockLevel
    daily_demand: Decimal
    days_until_stockout: float
    projected_stockout_date: datetime
    recommended_reorder_date: datetime
    recommended_order: int


@dataclass(slots=True)
class InventoryForecastResult:
    generated_at: datetime
    expires_at: datetime
    ttl_minutes: int
    lookback_days: int
    lead_time_days: int
    safety_stock_days: int
    forecasts: list[ForecastInsight]


class GetInventoryForecastUseCase:
    def __init__(
        self,
        product_repo: ProductRepository,
        inventory_repo: InventoryMovementRepository,
    ) -> None:
        self._product_repo = product_repo
        self._inventory_repo = inventory_repo

    async def execute(self, data: InventoryForecastInput) -> InventoryForecastResult:
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=data.lookback_days)
        ttl_minutes = max(1, data.ttl_minutes)
        expires_at = now + timedelta(minutes=ttl_minutes)

        products = await self._collect_products()
        forecasts: list[ForecastInsight] = []

        for product in products:
            stock = await self._inventory_repo.get_stock_level(product.id)
            outflow_qty = await self._inventory_repo.get_outflow_since(product.id, lookback_start)
            daily_demand = Decimal(outflow_qty) / Decimal(max(1, data.lookback_days))

            if daily_demand <= 0 and not data.include_zero_demand:
                continue

            # Avoid division by zero
            if daily_demand <= 0:
                days_until_stockout = float("inf")
                projected_stockout_date = datetime.max.replace(tzinfo=UTC)
                recommended_order = 0
                reorder_date = projected_stockout_date
            else:
                days_until_stockout = float(stock.quantity_on_hand) / float(daily_demand)
                projected_stockout_date = now + timedelta(days=days_until_stockout)
                reorder_point_value = daily_demand * Decimal(data.lead_time_days + data.safety_stock_days)
                reorder_point_units = ceil(reorder_point_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                recommended_order = max(0, reorder_point_units - stock.quantity_on_hand)
                reorder_date = projected_stockout_date - timedelta(days=data.lead_time_days)

            forecasts.append(
                ForecastInsight(
                    product=product,
                    stock=stock,
                    daily_demand=daily_demand,
                    days_until_stockout=days_until_stockout,
                    projected_stockout_date=projected_stockout_date,
                    recommended_reorder_date=reorder_date,
                    recommended_order=recommended_order,
                )
            )

        forecasts.sort(key=lambda f: f.days_until_stockout)

        return InventoryForecastResult(
            generated_at=now,
            expires_at=expires_at,
            ttl_minutes=ttl_minutes,
            lookback_days=data.lookback_days,
            lead_time_days=data.lead_time_days,
            safety_stock_days=data.safety_stock_days,
            forecasts=forecasts,
        )

    async def _collect_products(self) -> Sequence[Product]:
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
