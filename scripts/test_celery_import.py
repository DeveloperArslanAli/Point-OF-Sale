"""Test script for Phase 18.2: Product Import with Celery."""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import structlog
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.adapters.celery_import_scheduler import CeleryImportScheduler

logger = structlog.get_logger(__name__)


async def test_celery_scheduler():
    """Test the Celery import scheduler."""
    print("\n" + "="*60)
    print("Phase 18.2: Celery Product Import Test")
    print("="*60 + "\n")
    
    scheduler = CeleryImportScheduler()
    
    # Mock job object for testing
    class MockJob:
        def __init__(self):
            self.id = "test-job-123"
            self.total_rows = 100
    
    job = MockJob()
    
    print("1. Testing schedule_import...")
    try:
        task_id = await scheduler.schedule_import(job)
        print(f"   ✓ Import scheduled with task_id: {task_id}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        print("   Note: This is expected if Redis/Celery worker not running")
        return
    
    print("\n2. Testing get_task_status...")
    await asyncio.sleep(1)  # Give task time to start
    try:
        status = await scheduler.get_task_status(task_id)
        print(f"   Task state: {status['state']}")
        if status['result']:
            print(f"   Result: {status['result']}")
        if status['error']:
            print(f"   Error: {status['error']}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
    
    print("\n3. Celery Configuration Check...")
    print(f"   Broker: {celery_app.conf.broker_url}")
    print(f"   Backend: {celery_app.conf.result_backend}")
    print(f"   Queues: {[q.name for q in celery_app.conf.task_queues]}")
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)
    print("\nNext Steps:")
    print("1. Start Redis: docker-compose -f docker-compose.dev.yml up redis -d")
    print("2. Start Celery worker: cd backend; poetry run celery -A app.infrastructure.tasks.celery_app worker -l info")
    print("3. Start Flower: cd backend; poetry run celery -A app.infrastructure.tasks.celery_app flower")
    print("4. Test via API: POST /api/v1/products/import with CSV file")
    print("5. Monitor: http://localhost:5555 (Flower)")


if __name__ == "__main__":
    asyncio.run(test_celery_scheduler())
