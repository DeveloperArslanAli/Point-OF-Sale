"""Celery-based import scheduler adapter."""
from __future__ import annotations

import structlog
from celery.result import AsyncResult

from app.application.catalog.ports import ImportScheduler
from app.domain.catalog.import_job import ProductImportJob
from app.infrastructure.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


class CeleryImportScheduler(ImportScheduler):
    """Schedules product imports using Celery task queue."""
    
    async def enqueue(self, job: ProductImportJob) -> None:
        """Legacy method - schedules import without returning task_id."""
        await self.schedule_import(job)
    
    async def schedule_import(self, job: ProductImportJob) -> str:
        """
        Schedule a product import job for async processing.
        
        Args:
            job: The ProductImportJob to process
            
        Returns:
            task_id: Celery task ID for tracking
        """
        from app.infrastructure.tasks.product_import_tasks import process_product_import
        
        logger.info("scheduling_import_task", job_id=job.id, total_rows=job.total_rows)
        
        # Send task to Celery with routing to imports queue
        result = process_product_import.apply_async(
            args=[job.id],
            queue="imports",
            task_id=f"import-{job.id}",  # Use predictable task ID
        )
        
        logger.info("import_task_scheduled", job_id=job.id, task_id=result.id)
        return result.id
    
    async def get_task_status(self, task_id: str) -> dict[str, str | int | None]:
        """
        Get the current status of a Celery task.
        
        Args:
            task_id: The Celery task ID
            
        Returns:
            Dict with keys:
                - state: PENDING, STARTED, SUCCESS, FAILURE, RETRY
                - result: Task result if completed successfully
                - error: Error message if failed
        """
        result = AsyncResult(task_id, app=celery_app)
        
        response: dict[str, str | int | None] = {
            "state": result.state,
            "result": None,
            "error": None,
        }
        
        if result.successful():
            response["result"] = result.result
        elif result.failed():
            response["error"] = str(result.info)
        
        return response
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running Celery task.
        
        Args:
            task_id: The Celery task ID
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        try:
            celery_app.control.revoke(task_id, terminate=True)
            logger.info("task_cancelled", task_id=task_id)
            return True
        except Exception as exc:
            logger.error("task_cancellation_failed", task_id=task_id, error=str(exc))
            return False
