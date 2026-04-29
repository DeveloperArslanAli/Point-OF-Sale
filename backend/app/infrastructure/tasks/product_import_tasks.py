"""Celery tasks for product import processing."""
from __future__ import annotations

import structlog
from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.application.catalog.use_cases.process_product_import_job import (
    ProcessProductImportJobInput,
    ProcessProductImportJobUseCase,
)
from app.infrastructure.db.repositories.product_import_repository import (
    SqlAlchemyProductImportJobRepository,
)
from app.infrastructure.db.repositories.inventory_repository import (
    SqlAlchemyProductRepository,
)
from app.infrastructure.db.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


class AsyncTask(Task):
    """Base task that handles async execution in Celery."""
    
    def __call__(self, *args, **kwargs):
        """Run async tasks in sync context."""
        import asyncio
        return asyncio.run(self.run_async(*args, **kwargs))
    
    async def run_async(self, *args, **kwargs):
        """Override this method in subclasses."""
        raise NotImplementedError


@celery_app.task(bind=True, base=AsyncTask, name="process_product_import")
def process_product_import(self: AsyncTask, job_id: str) -> dict[str, str | int]:
    """
    Process a product import job asynchronously.
    
    Args:
        job_id: The ID of the ProductImportJob to process
        
    Returns:
        Dict with status, job_id, processed_count, failed_count
    """
    return self(*[job_id])  # Triggers __call__ which runs run_async


@process_product_import.run_async  # type: ignore
async def process_product_import_async(job_id: str) -> dict[str, str | int]:
    """Async implementation of product import processing."""
    bind_contextvars(trace_id=f"import-{job_id}", job_id=job_id)
    logger.info("celery_task_started", task="process_product_import", job_id=job_id)
    
    session: AsyncSession | None = None
    try:
        # Create async session
        session = async_session_factory()
        
        # Initialize repositories
        job_repo = SqlAlchemyProductImportJobRepository(session)
        product_repo = SqlAlchemyProductRepository(session)
        category_repo = SqlAlchemyCategoryRepository(session)
        
        # Execute use case
        use_case = ProcessProductImportJobUseCase(job_repo, product_repo, category_repo)
        result = await use_case.execute(ProcessProductImportJobInput(job_id=job_id))
        
        await session.commit()
        
        logger.info(
            "celery_task_completed",
            task="process_product_import",
            job_id=job_id,
            status=result.status,
            processed=result.processed_count,
            failed=result.failed_count,
        )
        
        return {
            "status": "success",
            "job_id": job_id,
            "processed_count": result.processed_count,
            "failed_count": result.failed_count,
        }
        
    except Exception as exc:
        if session:
            await session.rollback()
        logger.exception("celery_task_failed", task="process_product_import", job_id=job_id)
        raise
    finally:
        if session:
            await session.close()
        clear_contextvars()

