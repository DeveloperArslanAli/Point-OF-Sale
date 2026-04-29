"""Celery scheduled tasks for maintenance and periodic jobs."""
from __future__ import annotations

import structlog
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.auth.refresh_token_model import RefreshTokenModel
from app.infrastructure.db.models.product_import_job_model import ProductImportJobModel
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.product_import_tasks import AsyncTask
from app.infrastructure.tasks.report_tasks import generate_sales_report
from app.infrastructure.tasks.email_tasks import send_report_email
from app.infrastructure.tasks.inventory_tasks import (
    refresh_inventory_forecast,
    recompute_forecast_model,
    check_low_stock_alerts,
    check_dead_stock_alerts,
)

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, base=AsyncTask, name="cleanup_expired_tokens")
def cleanup_expired_tokens(self: AsyncTask) -> dict[str, int]:
    """
    Clean up expired refresh tokens from the database.
    
    Runs hourly via Celery Beat.
    
    Returns:
        Dict with count of deleted tokens
    """
    return self(*[])


@cleanup_expired_tokens.run_async  # type: ignore
async def cleanup_expired_tokens_async() -> dict[str, int]:
    """Async implementation of token cleanup."""
    logger.info("cleanup_expired_tokens_started")
    
    session: AsyncSession | None = None
    try:
        session = async_session_factory()
        
        # Delete expired tokens
        now = datetime.utcnow()
        stmt = delete(RefreshTokenModel).where(RefreshTokenModel.expires_at < now)
        result = await session.execute(stmt)
        await session.commit()
        
        deleted_count = result.rowcount or 0
        
        logger.info("cleanup_expired_tokens_completed", deleted_count=deleted_count)
        
        return {
            "deleted_count": deleted_count,
            "timestamp": now.isoformat(),
        }
        
    except Exception as exc:
        if session:
            await session.rollback()
        logger.exception("cleanup_expired_tokens_failed")
        raise
    finally:
        if session:
            await session.close()


@celery_app.task(bind=True, base=AsyncTask, name="cleanup_old_import_jobs")
def cleanup_old_import_jobs(self: AsyncTask, days_old: int = 30) -> dict[str, int]:
    """
    Clean up old completed/failed import jobs.
    
    Args:
        days_old: Delete jobs older than this many days (default: 30)
        
    Returns:
        Dict with count of deleted jobs
    """
    return self(*[days_old])


@cleanup_old_import_jobs.run_async  # type: ignore
async def cleanup_old_import_jobs_async(days_old: int = 30) -> dict[str, int]:
    """Async implementation of import job cleanup."""
    logger.info("cleanup_old_import_jobs_started", days_old=days_old)
    
    session: AsyncSession | None = None
    try:
        session = async_session_factory()
        
        # Delete old completed/failed jobs
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        stmt = delete(ProductImportJobModel).where(
            ProductImportJobModel.created_at < cutoff_date,
            ProductImportJobModel.status.in_(["completed", "failed"])
        )
        result = await session.execute(stmt)
        await session.commit()
        
        deleted_count = result.rowcount or 0
        
        logger.info("cleanup_old_import_jobs_completed", deleted_count=deleted_count)
        
        return {
            "deleted_count": deleted_count,
            "days_old": days_old,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as exc:
        if session:
            await session.rollback()
        logger.exception("cleanup_old_import_jobs_failed")
        raise
    finally:
        if session:
            await session.close()


@celery_app.task(name="generate_daily_reports")
def generate_daily_reports() -> dict[str, str]:
    """
    Generate and email daily sales reports.
    
    Runs daily at 11 PM via Celery Beat.
    Configured in celery_app.py beat_schedule.
    
    Returns:
        Dict with task IDs
    """
    logger.info("generate_daily_reports_started")
    
    # Calculate yesterday's date range
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    
    # Schedule sales report generation
    report_task = generate_sales_report.apply_async(
        args=[yesterday.isoformat(), yesterday.isoformat(), "json"],
        queue="reports"
    )
    
    # TODO: In production, chain email task:
    # report_task.then(send_report_email.s("admin@example.com", "sales"))
    
    logger.info("generate_daily_reports_scheduled", report_task_id=report_task.id)
    
    return {
        "status": "scheduled",
        "report_task_id": report_task.id,
        "report_date": yesterday.isoformat(),
    }


@celery_app.task(bind=True, base=AsyncTask, name="health_check_celery")
def health_check_celery(self: AsyncTask) -> dict[str, str]:
    """
    Health check task to verify Celery workers are operational.
    
    Can be called via API to check worker health.
    
    Returns:
        Dict with health status
    """
    return self(*[])


@health_check_celery.run_async  # type: ignore
async def health_check_celery_async() -> dict[str, str]:
    """Async implementation of health check."""
    logger.info("health_check_celery_executed")
    
    # Simple health check - if this executes, worker is healthy
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker": "celery-worker",
    }


@celery_app.task(bind=True, base=AsyncTask, name="database_health_check")
def database_health_check(self: AsyncTask) -> dict[str, str | bool]:
    """
    Check database connectivity.
    
    Returns:
        Dict with database health status
    """
    return self(*[])


@database_health_check.run_async  # type: ignore
async def database_health_check_async() -> dict[str, str | bool]:
    """Async implementation of database health check."""
    logger.info("database_health_check_started")
    
    session: AsyncSession | None = None
    try:
        session = async_session_factory()
        
        # Simple query to check connectivity
        result = await session.execute(select(1))
        result.scalar()
        
        logger.info("database_health_check_passed")
        
        return {
            "status": "healthy",
            "connected": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as exc:
        logger.error("database_health_check_failed", error=str(exc))
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(exc),
            "timestamp": datetime.utcnow().isoformat(),
        }
    finally:
        if session:
            await session.close()


# ==================== Inventory Intelligence Scheduled Tasks ====================

@celery_app.task(name="scheduled_inventory_forecast_refresh")
def scheduled_inventory_forecast_refresh() -> dict[str, str]:
    """
    Scheduled task to refresh inventory forecasts.
    
    Runs every 6 hours via Celery Beat to keep forecasts fresh.
    
    Returns:
        Dict with task status
    """
    logger.info("scheduled_inventory_forecast_refresh_started")
    
    # Trigger the forecast refresh
    task = refresh_inventory_forecast.apply_async(
        kwargs={
            "lookback_days": 60,
            "lead_time_days": 7,
            "safety_stock_days": 3,
            "include_zero_demand": False,
            "ttl_minutes": 360,
        }
    )
    
    logger.info("scheduled_inventory_forecast_refresh_queued", task_id=task.id)
    
    return {
        "status": "queued",
        "task_id": task.id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@celery_app.task(name="scheduled_low_stock_check")
def scheduled_low_stock_check(email_recipients: list[str] | None = None) -> dict[str, str]:
    """
    Scheduled task to check low stock and send alerts.
    
    Runs twice daily (8 AM and 4 PM) via Celery Beat.
    
    Args:
        email_recipients: Override default recipients from settings
        
    Returns:
        Dict with task status
    """
    logger.info("scheduled_low_stock_check_started")
    
    # Get default recipients from settings if not provided
    # In production, retrieve from settings.ALERT_EMAIL_RECIPIENTS
    recipients = email_recipients or []
    
    task = check_low_stock_alerts.apply_async(
        kwargs={
            "threshold_days": 7,
            "email_recipients": recipients,
            "enable_sms": False,  # SMS disabled by default
        }
    )
    
    logger.info("scheduled_low_stock_check_queued", task_id=task.id)
    
    return {
        "status": "queued",
        "task_id": task.id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@celery_app.task(name="scheduled_dead_stock_report")
def scheduled_dead_stock_report(email_recipients: list[str] | None = None) -> dict[str, str]:
    """
    Scheduled task to generate weekly dead stock report.
    
    Runs weekly on Monday at 9 AM via Celery Beat.
    
    Args:
        email_recipients: Override default recipients from settings
        
    Returns:
        Dict with task status
    """
    logger.info("scheduled_dead_stock_report_started")
    
    recipients = email_recipients or []
    
    task = check_dead_stock_alerts.apply_async(
        kwargs={
            "days_inactive": 90,
            "email_recipients": recipients,
        }
    )
    
    logger.info("scheduled_dead_stock_report_queued", task_id=task.id)
    
    return {
        "status": "queued",
        "task_id": task.id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@celery_app.task(name="scheduled_forecast_model_recompute")
def scheduled_forecast_model_recompute() -> dict[str, str]:
    """
    Scheduled task to recompute forecast model with advanced parameters.
    
    Runs nightly at 2 AM via Celery Beat when system load is low.
    
    Returns:
        Dict with task status
    """
    logger.info("scheduled_forecast_model_recompute_started")
    
    task = recompute_forecast_model.apply_async(
        kwargs={
            "smoothing_alpha": 0.3,
            "seasonality": False,
            "lookback_days": 90,
            "lead_time_days": 7,
            "safety_stock_days": 3,
        }
    )
    
    logger.info("scheduled_forecast_model_recompute_queued", task_id=task.id)
    
    return {
        "status": "queued",
        "task_id": task.id,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ==================== ML Model Scheduled Tasks (Phase 23) ====================

@celery_app.task(name="scheduled_ml_feature_extraction")
def scheduled_ml_feature_extraction() -> dict[str, str]:
    """
    Scheduled task to extract ML features for all models.
    
    Runs daily at 1 AM via Celery Beat.
    Populates Redis feature store with customer and product features.
    
    Returns:
        Dict with task status
    """
    from app.infrastructure.tasks.ml_data_pipeline import (
        extract_customer_features,
        extract_product_features,
    )
    
    logger.info("scheduled_ml_feature_extraction_started")
    
    # Extract customer features
    customer_task = extract_customer_features.apply_async(
        kwargs={
            "lookback_days": 365,
            "churn_threshold_days": 60,
        }
    )
    
    # Extract product features
    product_task = extract_product_features.apply_async(
        kwargs={
            "lookback_days": 90,
        }
    )
    
    logger.info(
        "scheduled_ml_feature_extraction_queued",
        customer_task_id=customer_task.id,
        product_task_id=product_task.id,
    )
    
    return {
        "status": "queued",
        "customer_task_id": customer_task.id,
        "product_task_id": product_task.id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@celery_app.task(name="scheduled_ml_model_training")
def scheduled_ml_model_training() -> dict[str, str]:
    """
    Scheduled task to retrain ML models.
    
    Runs weekly on Sunday at 3 AM via Celery Beat.
    Retrains churn, fraud, and recommendation models.
    
    Returns:
        Dict with task IDs
    """
    from app.infrastructure.tasks.ml_model_tasks import (
        train_churn_model,
        train_fraud_model,
        train_recommendation_model,
    )
    
    logger.info("scheduled_ml_model_training_started")
    
    # Train churn model
    churn_task = train_churn_model.apply_async(
        kwargs={
            "lookback_days": 365,
            "churn_threshold_days": 60,
        }
    )
    
    # Train fraud model
    fraud_task = train_fraud_model.apply_async(
        kwargs={
            "lookback_days": 90,
            "contamination": 0.01,
        }
    )
    
    # Train recommendation model
    rec_task = train_recommendation_model.apply_async(
        kwargs={
            "lookback_days": 180,
            "min_support": 0.01,
        }
    )
    
    logger.info(
        "scheduled_ml_model_training_queued",
        churn_task_id=churn_task.id,
        fraud_task_id=fraud_task.id,
        rec_task_id=rec_task.id,
    )
    
    return {
        "status": "queued",
        "churn_task_id": churn_task.id,
        "fraud_task_id": fraud_task.id,
        "rec_task_id": rec_task.id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@celery_app.task(name="scheduled_churn_risk_report")
def scheduled_churn_risk_report() -> dict[str, str]:
    """
    Scheduled task to generate churn risk report.
    
    Runs weekly on Monday at 8 AM via Celery Beat.
    Identifies high-risk customers for retention campaigns.
    
    Returns:
        Dict with task status
    """
    from app.infrastructure.tasks.ml_model_tasks import predict_churn
    
    logger.info("scheduled_churn_risk_report_started")
    
    task = predict_churn.apply_async(
        kwargs={
            "customer_ids": None,  # All customers
            "risk_threshold": 0.6,  # High risk only
        }
    )
    
    logger.info("scheduled_churn_risk_report_queued", task_id=task.id)
    
    return {
        "status": "queued",
        "task_id": task.id,
        "timestamp": datetime.utcnow().isoformat(),
    }
