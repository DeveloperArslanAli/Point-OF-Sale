from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ProductImportJobOut(BaseModel):
    id: str
    original_filename: str
    status: str
    total_rows: int
    processed_rows: int
    error_count: int
    errors: list[str]
    created_at: datetime
    updated_at: datetime
    task_id: str | None = None  # Celery task ID for async tracking

    model_config = dict(from_attributes=True)


class ProductImportItemOut(BaseModel):
    id: str
    row_number: int
    status: str
    payload: dict[str, Any]
    error_message: str | None

    model_config = dict(from_attributes=True)


class ProductImportJobItemsPageMetaOut(BaseModel):
    page: int
    limit: int
    total: int
    pages: int


class ProductImportJobDetailOut(ProductImportJobOut):
    items: list[ProductImportItemOut]
    meta: ProductImportJobItemsPageMetaOut


class ProductImportJobStatusOut(BaseModel):
    total_jobs: int
    pending: int
    queued: int
    processing: int
    completed: int
    failed: int
    errors: int
    last_jobs: list[ProductImportJobOut]


class ProductImportJobPageMetaOut(BaseModel):
    page: int
    limit: int
    total: int
    pages: int


class ProductImportJobListOut(BaseModel):
    items: list[ProductImportJobOut]
    meta: ProductImportJobPageMetaOut
