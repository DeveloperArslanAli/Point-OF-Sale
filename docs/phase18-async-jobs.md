# Phase 18: Async Job Processing - Implementation Guide

**Duration:** 1 Sprint (10 days)  
**Priority:** 🔴 CRITICAL (Blocks: Phase 11, 12, 14)  
**Team:** 1 Backend Engineer  

---

## 🎯 Objectives

Replace synchronous blocking operations with async task queue:
- Product CSV imports run in background
- Report generation doesn't block API
- Email sending is queued
- Scheduled cleanup jobs
- Retry failed operations automatically

---

## ✅ Prerequisites

- [ ] Redis running locally (`docker-compose.dev.yml`)
- [ ] PostgreSQL stable
- [ ] Existing product import use cases reviewed
- [ ] `celery` and `redis` packages added to `pyproject.toml`

---

## 📂 File Structure

```
backend/
  app/
    infrastructure/
      tasks/
        __init__.py              # Celery app initialization
        celery_app.py            # Celery configuration
        product_import_tasks.py  # Import job tasks
        report_tasks.py          # Report generation tasks
        email_tasks.py           # Email delivery tasks
        scheduled_tasks.py       # Cron-like jobs
    application/
      catalog/
        ports.py                 # Add ImportSchedulerPort
      common/
        task_manager.py          # Task status tracking
    api/
      routers/
        tasks_router.py          # Task monitoring endpoints
  tests/
    integration/
      tasks/
        test_product_import_tasks.py
        test_report_tasks.py
```

---

## 🔧 Implementation Steps

### **Day 1-2: Celery Infrastructure Setup**

#### 1. Install Dependencies

**File:** `backend/pyproject.toml`
```toml
[tool.poetry.dependencies]
celery = "^5.3.4"
redis = "^5.0.1"
flower = "^2.0.1"  # Optional: monitoring UI
```

Run: `poetry install`

#### 2. Create Celery App

**File:** `backend/app/infrastructure/tasks/celery_app.py`
```python
from celery import Celery
from app.core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "retail_pos",
    broker=settings.CELERY_BROKER_URL,  # redis://localhost:6379/0
    backend=settings.CELERY_RESULT_BACKEND,  # redis://localhost:6379/1
    include=[
        "app.infrastructure.tasks.product_import_tasks",
        "app.infrastructure.tasks.report_tasks",
        "app.infrastructure.tasks.email_tasks",
        "app.infrastructure.tasks.scheduled_tasks",
    ],
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes warning
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)

# Scheduled tasks (cron-like)
celery_app.conf.beat_schedule = {
    "cleanup-expired-tokens": {
        "task": "app.infrastructure.tasks.scheduled_tasks.cleanup_expired_tokens",
        "schedule": 3600.0,  # Every hour
    },
    "generate-daily-reports": {
        "task": "app.infrastructure.tasks.scheduled_tasks.generate_daily_reports",
        "schedule": crontab(hour=23, minute=0),  # 11 PM daily
    },
}
```

#### 3. Update Settings

**File:** `backend/app/core/settings.py`
```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Celery Configuration
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Celery broker URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
        description="Celery result backend URL"
    )
```

#### 4. Update Docker Compose

**File:** `docker-compose.dev.yml`
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - pos-network

  celery-worker:
    build:
      context: ./backend
      dockerfile: docker/Dockerfile
    command: celery -A app.infrastructure.tasks.celery_app worker --loglevel=info
    depends_on:
      - postgres
      - redis
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    networks:
      - pos-network

  celery-beat:
    build:
      context: ./backend
      dockerfile: docker/Dockerfile
    command: celery -A app.infrastructure.tasks.celery_app beat --loglevel=info
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    networks:
      - pos-network

  flower:
    build:
      context: ./backend
      dockerfile: docker/Dockerfile
    command: celery -A app.infrastructure.tasks.celery_app flower --port=5555
    ports:
      - "5555:5555"
    depends_on:
      - redis
      - celery-worker
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    networks:
      - pos-network

volumes:
  redis-data:
```

---

### **Day 3-4: Product Import Tasks**

#### 5. Create Import Scheduler Port

**File:** `backend/app/application/catalog/ports.py`
```python
from typing import Protocol

class ImportSchedulerPort(Protocol):
    """Port for scheduling product import jobs."""
    
    async def schedule_import(self, job_id: str) -> str:
        """Schedule an import job. Returns task ID."""
        ...
    
    async def get_task_status(self, task_id: str) -> dict:
        """Get status of a scheduled task."""
        ...
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        ...
```

#### 6. Create Celery Import Tasks

**File:** `backend/app/infrastructure/tasks/product_import_tasks.py`
```python
from celery import Task
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.db.repositories.product_import_repository import ProductImportRepository
from app.application.catalog.use_cases.process_product_import import ProcessProductImportUseCase
import structlog

logger = structlog.get_logger()


class ImportTask(Task):
    """Base task with database session."""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "task_failed",
            task_id=task_id,
            task_name=self.name,
            exception=str(exc),
        )


@celery_app.task(bind=True, base=ImportTask, name="process_product_import")
def process_product_import(self, job_id: str) -> dict:
    """
    Process a product import job asynchronously.
    
    Args:
        job_id: ProductImportJob ID
        
    Returns:
        dict with status, processed_count, error_count
    """
    import asyncio
    
    logger.info("import_task_started", job_id=job_id, task_id=self.request.id)
    
    async def _process():
        async with async_session_factory() as session:
            repo = ProductImportRepository(session)
            use_case = ProcessProductImportUseCase(repo)
            
            result = await use_case.execute(job_id)
            await session.commit()
            
            return {
                "status": "completed",
                "job_id": job_id,
                "total_rows": result.total_rows,
                "processed_rows": result.processed_rows,
                "error_count": result.error_count,
            }
    
    try:
        result = asyncio.run(_process())
        logger.info("import_task_completed", **result)
        return result
    except Exception as e:
        logger.error("import_task_error", job_id=job_id, error=str(e))
        # Update job status to failed in DB
        asyncio.run(_mark_job_failed(job_id, str(e)))
        raise


async def _mark_job_failed(job_id: str, error: str):
    """Mark import job as failed."""
    async with async_session_factory() as session:
        repo = ProductImportRepository(session)
        job = await repo.get_by_id(job_id)
        if job:
            job.status = "failed"
            job.errors.append(f"Task error: {error}")
            await session.commit()


@celery_app.task(name="retry_failed_import")
def retry_failed_import(job_id: str) -> dict:
    """Retry a failed import job."""
    logger.info("retry_import_task", job_id=job_id)
    return process_product_import.delay(job_id)
```

#### 7. Create Celery Import Scheduler

**File:** `backend/app/infrastructure/tasks/celery_import_scheduler.py`
```python
from app.application.catalog.ports import ImportSchedulerPort
from app.infrastructure.tasks.product_import_tasks import process_product_import
from celery.result import AsyncResult


class CeleryImportScheduler(ImportSchedulerPort):
    """Celery-based import scheduler."""
    
    async def schedule_import(self, job_id: str) -> str:
        """Schedule import job in Celery."""
        result = process_product_import.delay(job_id)
        return result.id
    
    async def get_task_status(self, task_id: str) -> dict:
        """Get Celery task status."""
        result = AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": result.state,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None,
        }
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel Celery task."""
        AsyncResult(task_id).revoke(terminate=True)
        return True
```

#### 8. Update Product Import Use Case

**File:** `backend/app/application/catalog/use_cases/queue_product_import.py`
```python
# Replace ImmediateImportScheduler with CeleryImportScheduler

from app.application.catalog.ports import ImportSchedulerPort
from dataclasses import dataclass

@dataclass
class QueueProductImportResult:
    job_id: str
    task_id: str  # NEW: Celery task ID


class QueueProductImportUseCase:
    def __init__(
        self,
        import_repo: ProductImportRepositoryPort,
        scheduler: ImportSchedulerPort,  # Inject Celery scheduler
    ):
        self.import_repo = import_repo
        self.scheduler = scheduler
    
    async def execute(self, input_: QueueProductImportInput) -> QueueProductImportResult:
        # ... create job entity ...
        
        await self.import_repo.add(job)
        
        # Schedule asynchronously
        task_id = await self.scheduler.schedule_import(job.id)
        
        return QueueProductImportResult(job_id=job.id, task_id=task_id)
```

#### 9. Update Products Router

**File:** `backend/app/api/routers/products_router.py`
```python
from app.infrastructure.tasks.celery_import_scheduler import CeleryImportScheduler

@router.post("/import", status_code=status.HTTP_202_ACCEPTED)
async def queue_product_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> dict:
    """Queue product import for async processing."""
    
    repo = ProductImportRepository(session)
    scheduler = CeleryImportScheduler()  # NEW
    use_case = QueueProductImportUseCase(repo, scheduler)
    
    result = await use_case.execute(...)
    await session.commit()
    
    return {
        "job_id": result.job_id,
        "task_id": result.task_id,  # NEW
        "status": "queued",
        "message": "Import job queued for processing",
    }
```

---

### **Day 5-6: Report Generation Tasks**

#### 10. Create Report Tasks

**File:** `backend/app/infrastructure/tasks/report_tasks.py`
```python
from celery import Task
from app.infrastructure.tasks.celery_app import celery_app
import structlog

logger = structlog.get_logger()


@celery_app.task(bind=True, name="generate_sales_report")
def generate_sales_report(self, report_id: str, params: dict) -> dict:
    """
    Generate sales report asynchronously.
    
    Args:
        report_id: Report ID to update
        params: Report parameters (date_from, date_to, format)
        
    Returns:
        dict with report_url, rows_count
    """
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from app.application.reports.use_cases.generate_sales_report import GenerateSalesReportUseCase
    
    logger.info("report_generation_started", report_id=report_id, params=params)
    
    async def _generate():
        async with async_session_factory() as session:
            # Use case generates PDF/Excel file
            use_case = GenerateSalesReportUseCase(session)
            result = await use_case.execute(report_id, params)
            await session.commit()
            return result
    
    try:
        result = asyncio.run(_generate())
        logger.info("report_generation_completed", report_id=report_id)
        return {
            "status": "completed",
            "report_id": report_id,
            "file_url": result.file_url,
            "rows_count": result.rows_count,
        }
    except Exception as e:
        logger.error("report_generation_error", report_id=report_id, error=str(e))
        raise


@celery_app.task(name="generate_inventory_report")
def generate_inventory_report(report_id: str, params: dict) -> dict:
    """Generate inventory report."""
    # Similar implementation
    pass
```

---

### **Day 7-8: Email & Scheduled Tasks**

#### 11. Create Email Tasks

**File:** `backend/app/infrastructure/tasks/email_tasks.py`
```python
from celery import Task
from app.infrastructure.tasks.celery_app import celery_app
import structlog

logger = structlog.get_logger()


@celery_app.task(bind=True, name="send_receipt_email", max_retries=3)
def send_receipt_email(self, sale_id: str, customer_email: str) -> dict:
    """
    Send receipt email asynchronously.
    
    Args:
        sale_id: Sale ID
        customer_email: Customer email address
        
    Returns:
        dict with status, message_id
    """
    import asyncio
    from app.infrastructure.email.email_service import EmailService
    
    logger.info("sending_receipt_email", sale_id=sale_id, email=customer_email)
    
    try:
        # Get email service (SMTP/SendGrid/etc)
        email_service = EmailService()
        
        # Generate receipt content
        async def _send():
            async with async_session_factory() as session:
                # Fetch sale, generate HTML
                sale = await get_sale_for_receipt(session, sale_id)
                html = generate_receipt_html(sale)
                
                message_id = await email_service.send_email(
                    to=customer_email,
                    subject=f"Receipt - Order #{sale.id[:8]}",
                    html_body=html,
                )
                return message_id
        
        message_id = asyncio.run(_send())
        logger.info("receipt_email_sent", sale_id=sale_id, message_id=message_id)
        
        return {"status": "sent", "message_id": message_id}
        
    except Exception as e:
        logger.error("receipt_email_error", sale_id=sale_id, error=str(e))
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="send_bulk_promotional_email")
def send_bulk_promotional_email(customer_ids: list[str], template: str, data: dict) -> dict:
    """Send promotional emails to customer list."""
    # Batch email sending
    pass
```

#### 12. Create Scheduled Tasks

**File:** `backend/app/infrastructure/tasks/scheduled_tasks.py`
```python
from celery import Task
from celery.schedules import crontab
from app.infrastructure.tasks.celery_app import celery_app
import structlog

logger = structlog.get_logger()


@celery_app.task(name="cleanup_expired_tokens")
def cleanup_expired_tokens() -> dict:
    """Clean up expired refresh tokens (runs hourly)."""
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from datetime import datetime, timedelta, UTC
    
    logger.info("cleanup_tokens_started")
    
    async def _cleanup():
        async with async_session_factory() as session:
            cutoff = datetime.now(UTC) - timedelta(days=30)
            
            result = await session.execute(
                delete(RefreshTokenModel).where(
                    RefreshTokenModel.created_at < cutoff
                )
            )
            await session.commit()
            return result.rowcount
    
    deleted_count = asyncio.run(_cleanup())
    logger.info("cleanup_tokens_completed", deleted_count=deleted_count)
    
    return {"deleted_count": deleted_count}


@celery_app.task(name="generate_daily_reports")
def generate_daily_reports() -> dict:
    """Generate end-of-day reports (runs at 11 PM)."""
    import asyncio
    
    logger.info("daily_reports_started")
    
    # Generate sales summary
    generate_sales_report.delay(
        report_id=f"daily_{datetime.now(UTC).date()}",
        params={"type": "daily_summary"}
    )
    
    # Generate inventory snapshot
    generate_inventory_report.delay(
        report_id=f"inventory_{datetime.now(UTC).date()}",
        params={"type": "snapshot"}
    )
    
    return {"status": "reports_queued"}
```

---

### **Day 9: Task Monitoring API**

#### 13. Create Task Monitoring Endpoints

**File:** `backend/app/api/routers/tasks_router.py`
```python
from fastapi import APIRouter, Depends
from celery.result import AsyncResult
from app.api.dependencies.auth import require_roles, ADMIN_ROLE
from app.domain.auth.entities import User

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    _: User = Depends(require_roles(*ADMIN_ROLE)),
) -> dict:
    """Get status of any Celery task."""
    result = AsyncResult(task_id)
    
    return {
        "task_id": task_id,
        "status": result.state,
        "result": result.result if result.ready() else None,
        "traceback": result.traceback if result.failed() else None,
        "progress": result.info.get("progress") if result.state == "PROGRESS" else None,
    }


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    _: User = Depends(require_roles(*ADMIN_ROLE)),
) -> dict:
    """Cancel a running task."""
    AsyncResult(task_id).revoke(terminate=True)
    return {"status": "cancelled", "task_id": task_id}


@router.get("/stats/workers")
async def get_worker_stats(
    _: User = Depends(require_roles(*ADMIN_ROLE)),
) -> dict:
    """Get Celery worker statistics."""
    from app.infrastructure.tasks.celery_app import celery_app
    
    stats = celery_app.control.inspect().stats()
    active = celery_app.control.inspect().active()
    
    return {
        "workers": stats,
        "active_tasks": active,
    }
```

---

### **Day 10: Testing & Documentation**

#### 14. Integration Tests

**File:** `backend/tests/integration/tasks/test_product_import_tasks.py`
```python
import pytest
from app.infrastructure.tasks.product_import_tasks import process_product_import
from app.infrastructure.db.repositories.product_import_repository import ProductImportRepository


@pytest.mark.asyncio
async def test_process_product_import_task_success(async_session):
    """Test product import task processes successfully."""
    # Arrange: Create import job
    repo = ProductImportRepository(async_session)
    job = ProductImportJob.create(...)
    await repo.add(job)
    await async_session.commit()
    
    # Act: Run task synchronously (no .delay() in tests)
    result = process_product_import(job.id)
    
    # Assert
    assert result["status"] == "completed"
    assert result["processed_rows"] > 0


@pytest.mark.asyncio
async def test_process_product_import_task_handles_errors(async_session):
    """Test task handles errors gracefully."""
    # Test with invalid data
    pass
```

#### 15. Update Documentation

**File:** `backend/README.md`
```markdown
## Running Celery Workers

### Development
```bash
# Terminal 1: Start Redis
docker-compose up redis

# Terminal 2: Start Celery worker
cd backend
poetry run celery -A app.infrastructure.tasks.celery_app worker --loglevel=info

# Terminal 3: Start Celery beat (for scheduled tasks)
poetry run celery -A app.infrastructure.tasks.celery_app beat --loglevel=info

# Terminal 4: Start Flower (monitoring UI)
poetry run celery -A app.infrastructure.tasks.celery_app flower
# Visit http://localhost:5555
```

### Production
Use Docker Compose or Kubernetes deployment with proper scaling.
```

---

## 🧪 Testing Checklist

- [ ] Product import runs in background
- [ ] Task status can be queried
- [ ] Failed tasks can be retried
- [ ] Tasks timeout after 30 minutes
- [ ] Scheduled tasks run on schedule
- [ ] Email tasks retry on failure
- [ ] Worker crashes don't lose jobs (Redis persistence)
- [ ] Multiple workers can process concurrently
- [ ] Flower UI shows task history

---

## 📊 Acceptance Criteria

✅ **Must Have:**
1. Product imports don't block API responses
2. Import job status updates in real-time
3. Failed imports can be retried
4. Email sending is asynchronous
5. Daily reports generate automatically

✅ **Performance:**
- API responds < 200ms for queuing
- Worker processes 1000 products/minute
- Task queue handles 100 concurrent tasks

✅ **Reliability:**
- Failed tasks retry 3 times with backoff
- Redis persistence enabled
- Dead letter queue for permanent failures

---

## 🔄 Migration from Immediate Scheduler

**Before (Synchronous):**
```python
# Blocks for 5 minutes processing CSV
result = await process_import_use_case.execute(job_id)
return result  # Client waits 5 minutes
```

**After (Asynchronous):**
```python
# Returns immediately
task_id = await scheduler.schedule_import(job_id)
return {"job_id": job_id, "task_id": task_id}  # Client gets response in <100ms
```

---

## 📝 Next Steps

After Phase 18 completion:
- ✅ Proceed to **Phase 11** (Real-time) - Use Celery for event broadcasting
- ✅ Enhance **Phase 12** (POS) - Async receipt generation
- ✅ Build **Phase 14** (Reports) - Background report jobs

---

**Status:** Ready for implementation  
**Blockers:** None  
**Dependencies:** Redis must be running
