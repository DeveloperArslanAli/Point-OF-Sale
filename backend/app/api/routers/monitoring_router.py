"""API router for system monitoring and health checks."""
from __future__ import annotations

from typing import Any
from datetime import datetime

from fastapi import APIRouter, Depends, status
from celery.result import AsyncResult
from celery import states

from app.api.dependencies.auth import MANAGEMENT_ROLES, require_roles
from app.domain.auth.entities import User
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.scheduled_tasks import (
    health_check_celery,
    database_health_check,
    cleanup_expired_tokens,
    cleanup_old_import_jobs,
)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health", response_model=dict[str, Any])
async def health_check() -> dict[str, Any]:
    """
    Basic health check endpoint.
    
    No authentication required - used by load balancers.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "retail-pos-api",
    }


@router.get("/health/detailed", response_model=dict[str, Any])
async def detailed_health_check(
    _: User = Depends(require_roles(*MANAGEMENT_ROLES))
) -> dict[str, Any]:
    """
    Detailed health check with component status.
    
    Checks:
    - API server (implicit - if this runs, API is up)
    - Celery workers
    - Database connectivity
    """
    # Check Celery workers
    celery_health = await _check_celery_health()
    
    # Check database
    db_task = database_health_check.apply_async()
    try:
        db_health = db_task.get(timeout=5)
    except Exception as exc:
        db_health = {
            "status": "unhealthy",
            "error": str(exc),
        }
    
    # Aggregate status
    all_healthy = (
        celery_health["status"] == "healthy" and
        db_health["status"] == "healthy"
    )
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "api": {"status": "healthy"},
            "celery": celery_health,
            "database": db_health,
        },
    }


@router.get("/celery/workers", response_model=dict[str, Any])
async def get_celery_workers(
    _: User = Depends(require_roles(*MANAGEMENT_ROLES))
) -> dict[str, Any]:
    """Get list of active Celery workers."""
    inspect = celery_app.control.inspect()
    
    # Get active workers
    active_workers = inspect.active()
    stats = inspect.stats()
    
    if not active_workers:
        return {
            "status": "no_workers",
            "workers": [],
            "count": 0,
        }
    
    workers_info = []
    for worker_name, tasks in active_workers.items():
        worker_stats = stats.get(worker_name, {}) if stats else {}
        workers_info.append({
            "name": worker_name,
            "active_tasks": len(tasks),
            "stats": worker_stats,
        })
    
    return {
        "status": "active",
        "workers": workers_info,
        "count": len(workers_info),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/celery/queues", response_model=dict[str, Any])
async def get_celery_queues(
    _: User = Depends(require_roles(*MANAGEMENT_ROLES))
) -> dict[str, Any]:
    """Get Celery queue statistics."""
    inspect = celery_app.control.inspect()
    
    # Get reserved (pending) tasks per queue
    reserved = inspect.reserved()
    active = inspect.active()
    
    queues_info = {}
    
    if reserved:
        for worker, tasks in reserved.items():
            for task in tasks:
                queue = task.get("delivery_info", {}).get("routing_key", "default")
                if queue not in queues_info:
                    queues_info[queue] = {"pending": 0, "active": 0}
                queues_info[queue]["pending"] += 1
    
    if active:
        for worker, tasks in active.items():
            for task in tasks:
                queue = task.get("delivery_info", {}).get("routing_key", "default")
                if queue not in queues_info:
                    queues_info[queue] = {"pending": 0, "active": 0}
                queues_info[queue]["active"] += 1
    
    # Add configured queues
    for queue_name in ["imports", "reports", "emails", "default"]:
        if queue_name not in queues_info:
            queues_info[queue_name] = {"pending": 0, "active": 0}
    
    return {
        "queues": queues_info,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/celery/tasks/{task_id}", response_model=dict[str, Any])
async def get_task_info(
    task_id: str,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES))
) -> dict[str, Any]:
    """Get detailed information about a specific task."""
    result = AsyncResult(task_id, app=celery_app)
    
    info: dict[str, Any] = {
        "task_id": task_id,
        "state": result.state,
        "result": None,
        "error": None,
        "traceback": None,
    }
    
    if result.successful():
        info["result"] = result.result
    elif result.failed():
        info["error"] = str(result.info)
        info["traceback"] = result.traceback
    
    return info


@router.post("/maintenance/cleanup-tokens", response_model=dict[str, Any])
async def trigger_token_cleanup(
    _: User = Depends(require_roles(*MANAGEMENT_ROLES))
) -> dict[str, Any]:
    """Manually trigger expired token cleanup."""
    task = cleanup_expired_tokens.apply_async()
    
    return {
        "task_id": task.id,
        "status": "queued",
        "message": "Token cleanup started",
    }


@router.post("/maintenance/cleanup-imports", response_model=dict[str, Any])
async def trigger_import_cleanup(
    days_old: int = 30,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES))
) -> dict[str, Any]:
    """Manually trigger old import jobs cleanup."""
    task = cleanup_old_import_jobs.apply_async(args=[days_old])
    
    return {
        "task_id": task.id,
        "status": "queued",
        "message": f"Import cleanup started (jobs older than {days_old} days)",
    }


async def _check_celery_health() -> dict[str, Any]:
    """Internal helper to check Celery health."""
    try:
        # Send health check task
        task = health_check_celery.apply_async()
        result = task.get(timeout=5)
        
        return {
            "status": "healthy",
            "details": result,
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "error": str(exc),
        }
