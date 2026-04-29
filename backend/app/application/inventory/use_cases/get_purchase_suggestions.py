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
class PurchaseSuggestionsInput:
    lookback_days: int = 30
    lead_time_days: int = 7
    safety_stock_days: int = 2
    include_zero_demand: bool = False


@dataclass(slots=True)
class PurchaseSuggestion:
    product: Product
    stock: StockLevel
    daily_demand: Decimal
    reorder_point: int
    recommended_order: int
    lead_time_days: int
    unit_cost: Decimal
    currency: str
    estimated_cost: Decimal


@dataclass(slots=True)
class PurchaseSuggestionsResult:
    generated_at: datetime
    lookback_days: int
    lead_time_days: int
    safety_stock_days: int
    suggestions: list[PurchaseSuggestion]


class GetPurchaseSuggestionsUseCase:
    def __init__(
        self,
        product_repo: ProductRepository,
        inventory_repo: InventoryMovementRepository,
    ) -> None:
        self._product_repo = product_repo
        self._inventory_repo = inventory_repo

    async def execute(self, data: PurchaseSuggestionsInput) -> PurchaseSuggestionsResult:
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=data.lookback_days)

        products = await self._collect_products()
        suggestions: list[PurchaseSuggestion] = []

        for product in products:
            stock = await self._inventory_repo.get_stock_level(product.id)
            outflow_qty = await self._inventory_repo.get_outflow_since(product.id, lookback_start)
            daily_demand = Decimal(outflow_qty) / Decimal(max(1, data.lookback_days))

            if daily_demand <= 0 and not data.include_zero_demand:
                continue

            reorder_point_value = daily_demand * Decimal(data.lead_time_days + data.safety_stock_days)
            reorder_point_units = ceil(reorder_point_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            recommended_order = max(0, reorder_point_units - stock.quantity_on_hand)

            if recommended_order <= 0:
                continue

            unit_cost = product.purchase_price.amount
            estimated_cost = (Decimal(recommended_order) * unit_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            suggestions.append(
                PurchaseSuggestion(
                    product=product,
                    stock=stock,
                    daily_demand=daily_demand,
                    reorder_point=reorder_point_units,
                    recommended_order=recommended_order,
                    lead_time_days=data.lead_time_days,
                    unit_cost=unit_cost,
                    currency=product.purchase_price.currency,
                    estimated_cost=estimated_cost,
                )
            )

        suggestions.sort(key=lambda s: s.recommended_order, reverse=True)

        return PurchaseSuggestionsResult(
            generated_at=now,
            lookback_days=data.lookback_days,
            lead_time_days=data.lead_time_days,
            safety_stock_days=data.safety_stock_days,
            suggestions=suggestions,
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
