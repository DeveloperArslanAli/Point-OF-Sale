from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Sequence

from app.application.catalog.ports import ProductRepository
from app.application.inventory.ports import InventoryMovementRepository
from app.domain.catalog.entities import Product


@dataclass(slots=True)
class InventoryABCInput:
    lookback_days: int = 90
    a_threshold_percent: Decimal = Decimal("70")
    b_threshold_percent: Decimal = Decimal("90")


@dataclass(slots=True)
class ABCClassification:
    product: Product
    usage_quantity: int
    usage_value: Decimal
    cumulative_percent: Decimal
    abc_class: str


@dataclass(slots=True)
class InventoryABCResult:
    generated_at: datetime
    lookback_days: int
    a_threshold_percent: Decimal
    b_threshold_percent: Decimal
    classifications: list[ABCClassification]


class GetInventoryABCUseCase:
    def __init__(
        self,
        product_repo: ProductRepository,
        inventory_repo: InventoryMovementRepository,
    ) -> None:
        self._product_repo = product_repo
        self._inventory_repo = inventory_repo

    async def execute(self, data: InventoryABCInput) -> InventoryABCResult:
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=data.lookback_days)

        a_cutoff = data.a_threshold_percent
        b_cutoff = data.b_threshold_percent if data.b_threshold_percent >= a_cutoff else a_cutoff

        products = await self._collect_products()
        outflows = await self._inventory_repo.get_outflows_since(lookback_start)

        classifications: list[ABCClassification] = []

        # Compute usage values and sort descending by value
        usage_items: list[tuple[Product, int, Decimal]] = []
        for product in products:
            qty = outflows.get(product.id, 0)
            if qty <= 0:
                continue
            usage_value = Decimal(qty) * product.price_retail.amount
            usage_items.append((product, qty, usage_value))

        usage_items.sort(key=lambda item: item[2], reverse=True)
        total_value = sum((item[2] for item in usage_items), Decimal(0))

        if total_value == 0:
            return InventoryABCResult(
                generated_at=now,
                lookback_days=data.lookback_days,
                a_threshold_percent=data.a_threshold_percent,
                b_threshold_percent=data.b_threshold_percent,
                classifications=[],
            )

        cumulative_value = Decimal(0)
        for product, qty, usage_value in usage_items:
            cumulative_value += usage_value
            cumulative_percent = (cumulative_value / total_value) * Decimal(100)
            if cumulative_percent <= a_cutoff:
                klass = "A"
            elif cumulative_percent <= b_cutoff:
                klass = "B"
            else:
                klass = "C"

            classifications.append(
                ABCClassification(
                    product=product,
                    usage_quantity=qty,
                    usage_value=usage_value,
                    cumulative_percent=cumulative_percent.quantize(Decimal("0.01")),
                    abc_class=klass,
                )
            )

        return InventoryABCResult(
            generated_at=now,
            lookback_days=data.lookback_days,
            a_threshold_percent=a_cutoff,
            b_threshold_percent=b_cutoff,
            classifications=classifications,
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
