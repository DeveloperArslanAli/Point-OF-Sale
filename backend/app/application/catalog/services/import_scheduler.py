from __future__ import annotations

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.application.catalog.ports import ImportScheduler
from app.application.catalog.use_cases.process_product_import_job import (
    ProcessProductImportJobInput,
    ProcessProductImportJobUseCase,
)
from app.domain.catalog.import_job import ProductImportJob

logger = structlog.get_logger(__name__)


class LoggingImportScheduler(ImportScheduler):
    async def enqueue(self, job: ProductImportJob) -> None:  # pragma: no cover - side-effect only
        logger.info("product_import_job_enqueued", job_id=job.id, total_rows=job.total_rows)


class ImmediateImportScheduler(ImportScheduler):
    def __init__(self, processor: ProcessProductImportJobUseCase) -> None:
        self._processor = processor

    async def enqueue(self, job: ProductImportJob) -> None:
        bind_contextvars(trace_id=f"import-{job.id}")
        logger.info("product_import_job_processing", job_id=job.id)
        try:
            await self._processor.execute(ProcessProductImportJobInput(job_id=job.id))
        except Exception:
            logger.exception("product_import_job_failed", job_id=job.id)
            clear_contextvars()
            raise
        else:
            logger.info("product_import_job_processed", job_id=job.id)
            clear_contextvars()

    async def schedule_import(self, job: ProductImportJob) -> str | None:
        """Synchronous scheduler compatibility shim for Celery interface."""
        await self.enqueue(job)
        return None
