from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Mapping, Sequence

from app.application.catalog.ports import ProductRepository
from app.application.inventory.ports import InventoryMovementRepository
from app.application.inventory.use_cases.get_purchase_suggestions import (
    GetPurchaseSuggestionsUseCase,
    PurchaseSuggestionsInput,
    PurchaseSuggestion,
    PurchaseSuggestionsResult,
)
from app.application.purchases.ports import ProductSupplierOverride, PurchaseRepository
from app.application.suppliers.ports import SupplierRepository
from app.domain.common.errors import NotFoundError
from app.domain.suppliers import Supplier


@dataclass(slots=True)
class PurchaseDraftLine:
    product_id: str
    name: str
    sku: str
    quantity: int
    unit_cost: Decimal
    estimated_cost: Decimal
    currency: str


@dataclass(slots=True)
class PurchaseDraftResult:
    generated_at: datetime
    supplier: Supplier | None
    total_estimated: Decimal
    currency: str | None
    lines: list[PurchaseDraftLine]
    suggestions_meta: PurchaseSuggestionsResult
    budget_cap: Decimal | None
    capped: bool


class GeneratePurchaseDraftsUseCase:
    def __init__(
        self,
        product_repo: ProductRepository,
        inventory_repo: InventoryMovementRepository,
        supplier_repo: SupplierRepository,
        purchase_repo: PurchaseRepository,
    ) -> None:
        self._suggestions_uc = GetPurchaseSuggestionsUseCase(product_repo, inventory_repo)
        self._supplier_repo = supplier_repo
        self._purchase_repo = purchase_repo

    async def execute(
        self,
        *,
        supplier_id: str | None,
        suggestions_input: PurchaseSuggestionsInput,
        budget_cap: Decimal | None = None,
    ) -> PurchaseDraftResult:
        suggestions = await self._suggestions_uc.execute(suggestions_input)
        overrides_map = await self._purchase_repo.get_best_supplier_overrides(
            [s.product.id for s in suggestions.suggestions]
        )
        supplier = await self._pick_supplier(supplier_id, overrides_map)
        lines: list[PurchaseDraftLine] = []
        total_estimated = Decimal("0")
        currency: str | None = None
        capped = False

        for suggestion in suggestions.suggestions:
            override = overrides_map.get(suggestion.product.id)
            line_currency = override.currency if override else suggestion.currency
            currency = currency or line_currency

            if budget_cap is not None and budget_cap <= total_estimated:
                capped = True
                break

            unit_cost = override.unit_cost if override else suggestion.unit_cost
            line_quantity = suggestion.recommended_order
            line_estimated = (Decimal(line_quantity) * unit_cost).quantize(Decimal("0.01"))

            if budget_cap is not None and total_estimated + line_estimated > budget_cap:
                remaining = budget_cap - total_estimated
                max_units = int(remaining // unit_cost) if unit_cost > 0 else 0
                if max_units <= 0:
                    capped = True
                    break
                line_quantity = max_units
                line_estimated = (Decimal(max_units) * unit_cost).quantize(Decimal("0.01"))
                capped = True

            lines.append(
                PurchaseDraftLine(
                    product_id=suggestion.product.id,
                    name=suggestion.product.name,
                    sku=suggestion.product.sku,
                    quantity=line_quantity,
                    unit_cost=unit_cost,
                    estimated_cost=line_estimated,
                    currency=line_currency,
                )
            )
            total_estimated += line_estimated

            if capped:
                break

        total_estimated = total_estimated.quantize(Decimal("0.01"))

        return PurchaseDraftResult(
            generated_at=suggestions.generated_at,
            supplier=supplier,
            total_estimated=total_estimated,
            currency=currency,
            lines=lines,
            suggestions_meta=suggestions,
            budget_cap=budget_cap,
            capped=capped,
        )

    async def _pick_supplier(
        self,
        supplier_id: str | None,
        overrides_map: Mapping[str, ProductSupplierOverride],
    ) -> Supplier | None:
        if supplier_id:
            supplier = await self._supplier_repo.get_by_id(supplier_id)
            if supplier is None:
                raise NotFoundError("Supplier not found")
            return supplier

        # Prefer the supplier that appears most often in the override rankings
        if overrides_map:
            supplier_counts: dict[str, int] = {}
            lead_times: dict[str, Decimal] = {}
            for override in overrides_map.values():
                sup_id = getattr(override, "supplier_id", None)
                if not sup_id:
                    continue
                supplier_counts[sup_id] = supplier_counts.get(sup_id, 0) + 1
                lead_time = getattr(override, "average_lead_time_hours", None)
                if lead_time is not None:
                    existing = lead_times.get(sup_id)
                    lead_times[sup_id] = lead_time if existing is None else min(existing, lead_time)

            if supplier_counts:
                ranked = sorted(
                    supplier_counts.items(),
                    key=lambda kv: (
                        -kv[1],
                        lead_times.get(kv[0], Decimal("1e9")),
                    ),
                )
                chosen_id = ranked[0][0]
                supplier = await self._supplier_repo.get_by_id(chosen_id)
                if supplier:
                    return supplier

        performances = await self._purchase_repo.get_supplier_performance(limit=10)
        chosen_id: str | None = None
        if performances:
            sorted_perf = sorted(
                performances,
                key=lambda p: (
                    p.average_lead_time_hours if p.average_lead_time_hours is not None else Decimal("1e9"),
                    -p.total_orders,
                ),
            )
            chosen_id = sorted_perf[0].supplier_id

        if chosen_id:
            supplier = await self._supplier_repo.get_by_id(chosen_id)
            if supplier:
                return supplier

        suppliers, _total = await self._supplier_repo.list_suppliers(active=True, limit=1)
        if suppliers:
            return suppliers[0]
        return None
