from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.catalog.ports import ProductImportJobRepository
from app.core.tenant import get_current_tenant_id
from app.domain.catalog.import_job import ImportStatus, ProductImportItem, ProductImportJob
from app.infrastructure.db.models.product_import_job_model import (
    ProductImportItemModel,
    ProductImportJobModel,
)


class SqlAlchemyProductImportJobRepository(ProductImportJobRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    def _apply_tenant_filter(self, stmt: Select[Any]) -> Select[Any]:
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(ProductImportJobModel.tenant_id == tenant_id)
        return stmt

    async def add_job(self, job: ProductImportJob, items: Sequence[ProductImportItem]) -> None:
        tenant_id = get_current_tenant_id()
        job_model = ProductImportJobModel(
            id=job.id,
            tenant_id=tenant_id,
            original_filename=job.original_filename,
            status=job.status.value,
            total_rows=job.total_rows,
            processed_rows=job.processed_rows,
            error_count=job.error_count,
            errors=job.errors,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        self._session.add(job_model)
        for item in items:
            item_model = ProductImportItemModel(
                id=item.id,
                job_id=item.job_id,
                row_number=item.row_number,
                payload=item.payload,
                status=item.status.value,
                error_message=item.error_message,
            )
            self._session.add(item_model)
        await self._session.flush()

    async def get_job(self, job_id: str) -> ProductImportJob | None:
        stmt = select(ProductImportJobModel).where(ProductImportJobModel.id == job_id)
        stmt = self._apply_tenant_filter(stmt)
        res = await self._session.execute(stmt)
        model = res.scalar_one_or_none()
        if model is None:
            return None
        return ProductImportJob(
            id=model.id,
            original_filename=model.original_filename,
            status=ImportStatus(model.status),
            total_rows=model.total_rows,
            processed_rows=model.processed_rows,
            error_count=model.error_count,
            errors=list(model.errors or []),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_job_with_items(
        self,
        job_id: str,
    ) -> tuple[ProductImportJob, list[ProductImportItem]] | None:
        stmt = (
            select(ProductImportJobModel)
            .where(ProductImportJobModel.id == job_id)
            .options(selectinload(ProductImportJobModel.items))
        )
        stmt = self._apply_tenant_filter(stmt)
        res = await self._session.execute(stmt)
        model = res.scalar_one_or_none()
        if model is None:
            return None
        job = ProductImportJob(
            id=model.id,
            original_filename=model.original_filename,
            status=ImportStatus(model.status),
            total_rows=model.total_rows,
            processed_rows=model.processed_rows,
            error_count=model.error_count,
            errors=list(model.errors or []),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
        items = [
            ProductImportItem(
                id=item.id,
                job_id=item.job_id,
                row_number=item.row_number,
                payload=dict(item.payload or {}),
                status=ImportStatus(item.status),
                error_message=item.error_message,
            )
            for item in sorted(model.items, key=lambda entry: entry.row_number)
        ]
        return job, items

    async def save_job(self, job: ProductImportJob, items: Sequence[ProductImportItem]) -> None:
        job_model = await self._session.get(ProductImportJobModel, job.id)
        if job_model is None:
            return
        job_model.status = job.status.value
        job_model.total_rows = job.total_rows
        job_model.processed_rows = job.processed_rows
        job_model.error_count = job.error_count
        job_model.errors = list(job.errors)
        job_model.created_at = job.created_at
        job_model.updated_at = job.updated_at

        result = await self._session.execute(
            select(ProductImportItemModel).where(ProductImportItemModel.job_id == job.id)
        )
        existing_items = {item_model.id: item_model for item_model in result.scalars().all()}
        for item in items:
            model = existing_items.get(item.id)
            if model is None:
                continue
            model.status = item.status.value
            model.error_message = item.error_message
            model.payload = dict(item.payload)

        await self._session.flush()

    async def list_jobs(
        self,
        *,
        status: ImportStatus | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[Sequence[ProductImportJob], int]:
        stmt = select(ProductImportJobModel).order_by(ProductImportJobModel.created_at.desc())
        count_stmt = select(func.count(ProductImportJobModel.id))
        
        # Apply tenant filter
        stmt = self._apply_tenant_filter(stmt)
        tenant_id = get_current_tenant_id()
        if tenant_id:
            count_stmt = count_stmt.where(ProductImportJobModel.tenant_id == tenant_id)

        if status is not None:
            stmt = stmt.where(ProductImportJobModel.status == status.value)
            count_stmt = count_stmt.where(ProductImportJobModel.status == status.value)

        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        res = await self._session.execute(stmt)
        rows = res.scalars().all()

        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        jobs = [
            ProductImportJob(
                id=row.id,
                original_filename=row.original_filename,
                status=ImportStatus(row.status),
                total_rows=row.total_rows,
                processed_rows=row.processed_rows,
                error_count=row.error_count,
                errors=list(row.errors or []),
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return jobs, int(total)

    async def list_job_items(
        self,
        job_id: str,
        *,
        status: ImportStatus | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[Sequence[ProductImportItem], int]:
        stmt = (
            select(ProductImportItemModel)
            .where(ProductImportItemModel.job_id == job_id)
            .order_by(ProductImportItemModel.row_number.asc())
        )
        count_stmt = select(func.count(ProductImportItemModel.id)).where(ProductImportItemModel.job_id == job_id)

        if status is not None:
            stmt = stmt.where(ProductImportItemModel.status == status.value)
            count_stmt = count_stmt.where(ProductImportItemModel.status == status.value)

        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        res = await self._session.execute(stmt)
        rows = res.scalars().all()

        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        items = [
            ProductImportItem(
                id=row.id,
                job_id=row.job_id,
                row_number=row.row_number,
                payload=dict(row.payload or {}),
                status=ImportStatus(row.status),
                error_message=row.error_message,
            )
            for row in rows
        ]
        return items, int(total)
