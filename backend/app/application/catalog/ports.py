from __future__ import annotations

from decimal import Decimal
from typing import Protocol, Sequence

from app.domain.catalog.entities import Category, Product
from app.domain.catalog.import_job import ImportStatus, ProductImportItem, ProductImportJob


class ProductRepository(Protocol):
    async def add(self, product: Product) -> None: ...  # pragma: no cover - interface
    async def get_by_sku(self, sku: str) -> Product | None: ...  # pragma: no cover
    async def get_by_id(self, product_id: str, *, lock: bool = False) -> Product | None: ...  # pragma: no cover
    async def update(self, product: Product, *, expected_version: int) -> bool: ...  # pragma: no cover
    async def list_products(
        self,
        *,
        search: str | None = None,
        category_id: str | None = None,
        active: bool | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
        sort_by: str = "created_at",
        sort_direction: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Product], int]: ...  # pragma: no cover
    # Future: delete (soft) etc.


class CategoryRepository(Protocol):
    async def add(self, category: Category) -> None: ...  # pragma: no cover
    async def get_by_slug(self, slug: str) -> Category | None: ...  # pragma: no cover
    async def get_by_id(self, category_id: str) -> Category | None: ...  # pragma: no cover
    async def search(
        self,
        *,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Category], int]: ...  # pragma: no cover


class ProductImportJobRepository(Protocol):
    async def add_job(
        self,
        job: ProductImportJob,
        items: Sequence[ProductImportItem],
    ) -> None: ...  # pragma: no cover

    async def get_job(self, job_id: str) -> ProductImportJob | None: ...  # pragma: no cover

    async def get_job_with_items(
        self,
        job_id: str,
    ) -> tuple[ProductImportJob, Sequence[ProductImportItem]] | None: ...  # pragma: no cover

    async def save_job(
        self,
        job: ProductImportJob,
        items: Sequence[ProductImportItem],
    ) -> None: ...  # pragma: no cover
    async def list_jobs(
        self,
        *,
        status: ImportStatus | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[Sequence[ProductImportJob], int]: ...  # pragma: no cover
    async def list_job_items(
        self,
        job_id: str,
        *,
        status: ImportStatus | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[Sequence[ProductImportItem], int]: ...  # pragma: no cover


class ImportScheduler(Protocol):
    """Schedules product import jobs for async processing."""
    
    async def enqueue(self, job: ProductImportJob) -> None:
        """Legacy method for backward compatibility. Use schedule_import instead."""
        ...  # pragma: no cover
    
    async def schedule_import(self, job: ProductImportJob) -> str:
        """Schedule an import job and return the task ID for tracking."""
        ...  # pragma: no cover
    
    async def get_task_status(self, task_id: str) -> dict[str, str | int | None]:
        """
        Get the status of an async task.
        
        Returns dict with keys: state, result, error
        """
        ...  # pragma: no cover
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task. Returns True if successful."""
        ...  # pragma: no cover

