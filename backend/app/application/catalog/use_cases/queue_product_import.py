from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from app.application.catalog.import_utils import parse_decimal
from app.application.catalog.ports import (
    CategoryRepository,
    ImportScheduler,
    ProductImportJobRepository,
    ProductRepository,
)
from app.domain.catalog.entities import Product
from app.domain.catalog.import_job import ProductImportItem, ProductImportJob
from app.domain.common.errors import NotFoundError, ValidationError

EXPECTED_COLUMNS = {"name", "sku", "retail_price", "purchase_price", "currency", "category_id"}


@dataclass(slots=True)
class QueueProductImportInput:
    filename: str
    content: bytes


@dataclass(slots=True)
class QueueProductImportResult:
    """Result of queueing a product import."""
    job: ProductImportJob
    task_id: str | None = None  # None for non-Celery schedulers


class QueueProductImportUseCase:
    def __init__(
        self,
        job_repo: ProductImportJobRepository,
        product_repo: ProductRepository,
        category_repo: CategoryRepository,
        scheduler: ImportScheduler,
    ) -> None:
        self._job_repo = job_repo
        self._product_repo = product_repo
        self._category_repo = category_repo
        self._scheduler = scheduler

    async def execute(self, data: QueueProductImportInput) -> QueueProductImportResult:
        rows = self._parse_rows(data)
        await self._validate_rows(rows)

        job = ProductImportJob.create(data.filename, total_rows=len(rows))
        items = [ProductImportItem.create(job.id, idx + 1, row) for idx, row in enumerate(rows)]

        await self._job_repo.add_job(job, items)
        
        # Try to use new schedule_import method, fall back to enqueue for compatibility
        task_id: str | None = None
        if hasattr(self._scheduler, 'schedule_import'):
            task_id = await self._scheduler.schedule_import(job)
        else:
            await self._scheduler.enqueue(job)
        
        refreshed = await self._job_repo.get_job(job.id)
        return QueueProductImportResult(job=refreshed or job, task_id=task_id)

    def _parse_rows(self, data: QueueProductImportInput) -> list[dict[str, str]]:
        try:
            text = data.content.decode("utf-8")
        except UnicodeDecodeError as exc:  # pragma: no cover - defensive
            raise ValidationError("File must be UTF-8 encoded") from exc
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise ValidationError("CSV header missing")
        missing = EXPECTED_COLUMNS - set(name.strip() for name in reader.fieldnames)
        if missing:
            raise ValidationError(f"CSV missing columns: {', '.join(sorted(missing))}")
        rows: list[dict[str, str]] = []
        for row in reader:
            if not any(value and value.strip() for value in row.values()):
                continue
            rows.append({key: (value or "").strip() for key, value in row.items()})
        if not rows:
            raise ValidationError("CSV file contains no data rows")
        return rows

    async def _validate_rows(self, rows: list[dict[str, str]]) -> None:
        seen_skus: set[str] = set()
        for idx, row in enumerate(rows, start=1):
            sku = row.get("sku", "")
            if not sku:
                raise ValidationError(f"Row {idx}: SKU required")
            if sku in seen_skus:
                raise ValidationError(f"Row {idx}: duplicate SKU '{sku}' in file")
            seen_skus.add(sku)

            retail = parse_decimal(row.get("retail_price", ""), idx, "retail_price", positive=True)
            purchase = parse_decimal(row.get("purchase_price", ""), idx, "purchase_price", positive_or_zero=True)

            category_id = row.get("category_id") or None
            if category_id:
                category = await self._category_repo.get_by_id(category_id)
                if category is None:
                    raise NotFoundError(f"Row {idx}: category '{category_id}' not found")

            try:
                Product.create(
                    name=row.get("name", ""),
                    sku=sku,
                    price_retail=retail,
                    purchase_price=purchase,
                    currency=row.get("currency") or "USD",
                    category_id=category_id,
                )
            except ValidationError as exc:
                raise ValidationError(f"Row {idx}: {exc.message}") from exc


