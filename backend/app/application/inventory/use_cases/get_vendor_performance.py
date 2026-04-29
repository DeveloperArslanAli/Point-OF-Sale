from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.application.purchases.ports import PurchaseRepository, SupplierPerformance
from app.application.suppliers.ports import SupplierRepository
from app.domain.suppliers import Supplier


@dataclass(slots=True)
class VendorPerformanceResult:
    supplier: Supplier
    performance: SupplierPerformance


class GetVendorPerformanceUseCase:
    def __init__(self, supplier_repo: SupplierRepository, purchase_repo: PurchaseRepository) -> None:
        self._supplier_repo = supplier_repo
        self._purchase_repo = purchase_repo

    async def execute(self, *, limit: int = 50) -> Sequence[VendorPerformanceResult]:
        performances = await self._purchase_repo.get_supplier_performance(limit=limit)
        results: list[VendorPerformanceResult] = []
        for perf in performances:
            supplier = await self._supplier_repo.get_by_id(perf.supplier_id)
            if supplier is None:
                continue
            results.append(VendorPerformanceResult(supplier=supplier, performance=perf))
        return results
