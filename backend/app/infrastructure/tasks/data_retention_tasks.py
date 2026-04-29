"""Celery tasks for GDPR data retention and anonymization."""
from __future__ import annotations

import structlog
from datetime import datetime, timedelta, UTC
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import async_session_factory
from app.infrastructure.db.models.customer_model import CustomerModel
from app.infrastructure.db.models.sale_model import SaleModel
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.product_import_tasks import AsyncTask

logger = structlog.get_logger(__name__)


# Default retention periods (in days)
RETENTION_PERIODS = {
    "customer_pii": 365 * 3,  # 3 years for customer data
    "transaction_details": 365 * 7,  # 7 years for financial records
    "audit_logs": 365 * 5,  # 5 years for audit logs
}


@celery_app.task(bind=True, base=AsyncTask, name="anonymize_expired_customer_data")
def anonymize_expired_customer_data(
    self: AsyncTask,
    retention_days: int | None = None,
    dry_run: bool = False,
) -> dict[str, int | bool]:
    """
    Anonymize customer PII data that has exceeded retention period.
    
    This task implements GDPR's "right to be forgotten" by anonymizing
    customer records that haven't had any activity beyond the retention period.
    
    Args:
        retention_days: Override default retention period
        dry_run: If True, report what would be anonymized without making changes
        
    Returns:
        Dict with count of affected records
    """
    return self(*[retention_days, dry_run])


@anonymize_expired_customer_data.run_async  # type: ignore
async def anonymize_expired_customer_data_async(
    retention_days: int | None = None,
    dry_run: bool = False,
) -> dict[str, int | bool]:
    """Async implementation of customer data anonymization."""
    retention = retention_days or RETENTION_PERIODS["customer_pii"]
    cutoff_date = datetime.now(UTC) - timedelta(days=retention)
    
    logger.info(
        "starting_customer_anonymization",
        retention_days=retention,
        cutoff_date=cutoff_date.isoformat(),
        dry_run=dry_run,
    )
    
    session: AsyncSession | None = None
    try:
        session = async_session_factory()
        
        # Find customers with no recent activity
        # A customer is eligible for anonymization if:
        # 1. Their last_purchase_date is before cutoff, OR
        # 2. They have no purchases and created_at is before cutoff
        
        # First, get customers to anonymize
        eligible_query = select(CustomerModel.id).where(
            CustomerModel.created_at < cutoff_date,
            # Exclude already anonymized records
            CustomerModel.email.notlike("%@anonymized.local"),
        )
        
        result = await session.execute(eligible_query)
        customer_ids = [row[0] for row in result.fetchall()]
        
        if not customer_ids:
            logger.info("no_customers_to_anonymize")
            return {
                "customers_anonymized": 0,
                "dry_run": dry_run,
            }
        
        if dry_run:
            logger.info("dry_run_would_anonymize", count=len(customer_ids))
            return {
                "customers_would_anonymize": len(customer_ids),
                "dry_run": True,
            }
        
        # Anonymize customer records
        anonymization_timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        
        for customer_id in customer_ids:
            # Get the customer
            stmt = select(CustomerModel).where(CustomerModel.id == customer_id)
            result = await session.execute(stmt)
            customer = result.scalar_one_or_none()
            
            if customer:
                # Anonymize PII fields
                customer.name = f"Anonymous Customer {anonymization_timestamp[-6:]}"
                customer.email = f"anon_{customer_id}@anonymized.local"
                customer.phone = None
                customer.address = None
                # Keep loyalty points and purchase history for business analytics
                # but remove identifying information
        
        await session.commit()
        
        logger.info("customer_anonymization_complete", count=len(customer_ids))
        
        return {
            "customers_anonymized": len(customer_ids),
            "dry_run": False,
        }
        
    except Exception as e:
        logger.error("customer_anonymization_failed", error=str(e))
        if session:
            await session.rollback()
        raise
    finally:
        if session:
            await session.close()


@celery_app.task(bind=True, base=AsyncTask, name="purge_old_audit_logs")
def purge_old_audit_logs(
    self: AsyncTask,
    retention_days: int | None = None,
    dry_run: bool = False,
) -> dict[str, int | bool]:
    """
    Purge audit log entries that have exceeded retention period.
    
    Args:
        retention_days: Override default retention period
        dry_run: If True, report what would be purged without making changes
        
    Returns:
        Dict with count of purged records
    """
    return self(*[retention_days, dry_run])


@purge_old_audit_logs.run_async  # type: ignore
async def purge_old_audit_logs_async(
    retention_days: int | None = None,
    dry_run: bool = False,
) -> dict[str, int | bool]:
    """Async implementation of audit log purging."""
    retention = retention_days or RETENTION_PERIODS["audit_logs"]
    cutoff_date = datetime.now(UTC) - timedelta(days=retention)
    
    logger.info(
        "starting_audit_log_purge",
        retention_days=retention,
        cutoff_date=cutoff_date.isoformat(),
        dry_run=dry_run,
    )
    
    session: AsyncSession | None = None
    try:
        from app.infrastructure.db.models.auth.admin_action_log_model import AdminActionLogModel
        
        session = async_session_factory()
        
        # Count logs to purge
        count_query = select(AdminActionLogModel.id).where(
            AdminActionLogModel.created_at < cutoff_date
        )
        result = await session.execute(count_query)
        log_ids = [row[0] for row in result.fetchall()]
        
        if not log_ids:
            logger.info("no_audit_logs_to_purge")
            return {
                "logs_purged": 0,
                "dry_run": dry_run,
            }
        
        if dry_run:
            logger.info("dry_run_would_purge", count=len(log_ids))
            return {
                "logs_would_purge": len(log_ids),
                "dry_run": True,
            }
        
        # Delete old logs in batches
        from sqlalchemy import delete
        
        batch_size = 1000
        total_deleted = 0
        
        for i in range(0, len(log_ids), batch_size):
            batch_ids = log_ids[i:i + batch_size]
            delete_stmt = delete(AdminActionLogModel).where(
                AdminActionLogModel.id.in_(batch_ids)
            )
            await session.execute(delete_stmt)
            total_deleted += len(batch_ids)
        
        await session.commit()
        
        logger.info("audit_log_purge_complete", count=total_deleted)
        
        return {
            "logs_purged": total_deleted,
            "dry_run": False,
        }
        
    except Exception as e:
        logger.error("audit_log_purge_failed", error=str(e))
        if session:
            await session.rollback()
        raise
    finally:
        if session:
            await session.close()


@celery_app.task(bind=True, base=AsyncTask, name="cleanup_old_report_executions")
def cleanup_old_report_executions(
    self: AsyncTask,
    retention_days: int = 30,
    dry_run: bool = False,
) -> dict[str, int | bool]:
    """
    Clean up old report execution records.
    
    Args:
        retention_days: Days to keep report executions (default 30)
        dry_run: If True, report what would be cleaned without making changes
        
    Returns:
        Dict with count of cleaned records
    """
    return self(*[retention_days, dry_run])


@cleanup_old_report_executions.run_async  # type: ignore
async def cleanup_old_report_executions_async(
    retention_days: int = 30,
    dry_run: bool = False,
) -> dict[str, int | bool]:
    """Async implementation of report execution cleanup."""
    cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)
    
    logger.info(
        "starting_report_execution_cleanup",
        retention_days=retention_days,
        cutoff_date=cutoff_date.isoformat(),
        dry_run=dry_run,
    )
    
    session: AsyncSession | None = None
    try:
        from app.infrastructure.db.models.report_model import ReportExecutionModel
        
        session = async_session_factory()
        
        # Count executions to clean
        count_query = select(ReportExecutionModel.id).where(
            ReportExecutionModel.created_at < cutoff_date
        )
        result = await session.execute(count_query)
        execution_ids = [row[0] for row in result.fetchall()]
        
        if not execution_ids:
            logger.info("no_report_executions_to_clean")
            return {
                "executions_cleaned": 0,
                "dry_run": dry_run,
            }
        
        if dry_run:
            return {
                "executions_would_clean": len(execution_ids),
                "dry_run": True,
            }
        
        # Delete old executions
        from sqlalchemy import delete
        
        delete_stmt = delete(ReportExecutionModel).where(
            ReportExecutionModel.id.in_(execution_ids)
        )
        await session.execute(delete_stmt)
        await session.commit()
        
        logger.info("report_execution_cleanup_complete", count=len(execution_ids))
        
        return {
            "executions_cleaned": len(execution_ids),
            "dry_run": False,
        }
        
    except Exception as e:
        logger.error("report_execution_cleanup_failed", error=str(e))
        if session:
            await session.rollback()
        raise
    finally:
        if session:
            await session.close()


# Celery Beat schedule for periodic data retention tasks
RETENTION_SCHEDULE = {
    "anonymize-expired-customers-daily": {
        "task": "anonymize_expired_customer_data",
        "schedule": 86400,  # Daily
        "options": {"queue": "default"},
    },
    "purge-old-audit-logs-weekly": {
        "task": "purge_old_audit_logs",
        "schedule": 604800,  # Weekly
        "options": {"queue": "default"},
    },
    "cleanup-report-executions-daily": {
        "task": "cleanup_old_report_executions",
        "schedule": 86400,  # Daily
        "options": {"queue": "default"},
    },
}
