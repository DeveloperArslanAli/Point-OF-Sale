"""Celery tasks for report generation."""
from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.reports.entities import ScheduleFrequency
from app.infrastructure.db.models.product_model import ProductModel
from app.infrastructure.db.models.report_model import ReportDefinitionModel
from app.infrastructure.db.models.sale_model import SaleItemModel, SaleModel
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.product_import_tasks import AsyncTask

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, base=AsyncTask, name="generate_sales_report")
def generate_sales_report(
    self: AsyncTask, 
    start_date: str, 
    end_date: str,
    format: str = "json"
) -> dict[str, str | int | list]:
    """
    Generate sales report for date range.
    
    Args:
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)
        format: Report format - 'json' or 'csv'
        
    Returns:
        Dict with report data and metadata
    """
    return self(*[start_date, end_date, format])


@generate_sales_report.run_async  # type: ignore
async def generate_sales_report_async(
    start_date: str, 
    end_date: str,
    format: str = "json"
) -> dict[str, str | int | list]:
    """Async implementation of sales report generation."""
    logger.info("generating_sales_report", start_date=start_date, end_date=end_date, format=format)
    
    session: AsyncSession | None = None
    try:
        session = async_session_factory()
        
        # Parse dates
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        # Query sales summary
        stmt = (
            select(
                func.count(SaleModel.id).label("total_sales"),
                func.sum(SaleModel.total_amount).label("total_revenue"),
                func.avg(SaleModel.total_amount).label("avg_sale_amount"),
            )
            .where(SaleModel.created_at >= start_dt)
            .where(SaleModel.created_at <= end_dt)
        )
        result = await session.execute(stmt)
        summary = result.one()
        
        # Query top products
        top_products_stmt = (
            select(
                ProductModel.name,
                ProductModel.sku,
                func.sum(SaleItemModel.quantity).label("total_quantity"),
                func.sum(SaleItemModel.total_price).label("total_revenue"),
            )
            .join(SaleItemModel, ProductModel.id == SaleItemModel.product_id)
            .join(SaleModel, SaleItemModel.sale_id == SaleModel.id)
            .where(SaleModel.created_at >= start_dt)
            .where(SaleModel.created_at <= end_dt)
            .group_by(ProductModel.id, ProductModel.name, ProductModel.sku)
            .order_by(func.sum(SaleItemModel.total_price).desc())
            .limit(10)
        )
        top_products_result = await session.execute(top_products_stmt)
        top_products = [
            {
                "name": row.name,
                "sku": row.sku,
                "quantity": int(row.total_quantity),
                "revenue": float(row.total_revenue),
            }
            for row in top_products_result.all()
        ]
        
        report_data = {
            "period": {"start": start_date, "end": end_date},
            "summary": {
                "total_sales": int(summary.total_sales or 0),
                "total_revenue": float(summary.total_revenue or 0),
                "avg_sale_amount": float(summary.avg_sale_amount or 0),
            },
            "top_products": top_products,
            "generated_at": datetime.utcnow().isoformat(),
            "format": format,
        }
        
        logger.info(
            "sales_report_generated",
            total_sales=report_data["summary"]["total_sales"],
            total_revenue=report_data["summary"]["total_revenue"],
        )
        
        return report_data
        
    except Exception:
        logger.exception("sales_report_generation_failed", start_date=start_date, end_date=end_date)
        raise
    finally:
        if session:
            await session.close()


@celery_app.task(bind=True, base=AsyncTask, name="generate_inventory_report")
def generate_inventory_report(self: AsyncTask) -> dict[str, str | int | list]:
    """
    Generate current inventory status report.
    
    Returns:
        Dict with inventory metrics
    """
    return self(*[])


@generate_inventory_report.run_async  # type: ignore
async def generate_inventory_report_async() -> dict[str, str | int | list]:
    """Async implementation of inventory report generation."""
    logger.info("generating_inventory_report")
    
    session: AsyncSession | None = None
    try:
        session = async_session_factory()
        
        # Query product counts by status
        active_stmt = select(func.count(ProductModel.id)).where(ProductModel.is_active == True)  # noqa: E712
        active_result = await session.execute(active_stmt)
        active_count = active_result.scalar() or 0
        
        inactive_stmt = select(func.count(ProductModel.id)).where(ProductModel.is_active == False)  # noqa: E712
        inactive_result = await session.execute(inactive_stmt)
        inactive_count = inactive_result.scalar() or 0
        
        # Query low stock items (would need stock level table for accurate data)
        # For now, just return product counts
        
        report_data = {
            "summary": {
                "total_products": int(active_count + inactive_count),
                "active_products": int(active_count),
                "inactive_products": int(inactive_count),
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
        
        logger.info("inventory_report_generated", total_products=report_data["summary"]["total_products"])
        
        return report_data
        
    except Exception:
        logger.exception("inventory_report_generation_failed")
        raise
    finally:
        if session:
            await session.close()


@celery_app.task(bind=True, base=AsyncTask, name="run_scheduled_reports")
def run_scheduled_reports(self: AsyncTask) -> dict[str, int]:
    """
    Check and run all due scheduled reports.
    
    This task should be run periodically (e.g., every 5 minutes) via Celery Beat.
    It checks all scheduled report definitions and generates reports for any
    that are due to run.
    
    Returns:
        Dict with counts of processed and failed reports
    """
    return self(*[])


@run_scheduled_reports.run_async  # type: ignore
async def run_scheduled_reports_async() -> dict[str, int]:
    """Async implementation of scheduled report runner."""
    logger.info("checking_scheduled_reports")
    
    session: AsyncSession | None = None
    processed = 0
    failed = 0
    
    try:
        session = async_session_factory()
        now = datetime.utcnow()
        
        # Query all report definitions with schedules
        # Schedule is stored as JSON, so we check if schedule is not null
        stmt = select(ReportDefinitionModel).where(
            ReportDefinitionModel.schedule != None  # noqa: E711
        )
        
        result = await session.execute(stmt)
        all_scheduled = result.scalars().all()
        
        # Filter to those that are due
        due_reports = []
        for report_def in all_scheduled:
            schedule = report_def.schedule
            if not schedule:
                continue
            
            # Check if schedule is enabled
            if not schedule.get("enabled", True):
                continue
            
            # Check if it's due to run
            next_run_str = schedule.get("next_run_at")
            if next_run_str:
                try:
                    next_run = datetime.fromisoformat(next_run_str.replace("Z", "+00:00"))
                    if next_run > now:
                        continue  # Not yet due
                except (ValueError, TypeError):
                    pass  # Invalid date, run it
            
            due_reports.append(report_def)
        
        for report_def in due_reports:
            try:
                schedule = report_def.schedule or {}
                logger.info(
                    "running_scheduled_report",
                    report_id=report_def.id,
                    report_name=report_def.name,
                )
                
                # Calculate next run time based on frequency
                next_run = _calculate_next_run(
                    frequency=schedule.get("frequency"),
                    day_of_week=schedule.get("day_of_week"),
                    day_of_month=schedule.get("day_of_month"),
                    time_of_day=schedule.get("time_of_day", "00:00"),
                    current_time=now,
                )
                
                # Update schedule with next run time
                schedule["next_run_at"] = next_run.isoformat() if next_run else None
                report_def.schedule = schedule
                
                # Send email to recipients if configured
                recipients = schedule.get("recipients", [])
                if recipients:
                    logger.info(
                        "sending_scheduled_report_email",
                        report_id=report_def.id,
                        recipients=recipients,
                    )
                    # In production, integrate with email service
                    # await email_service.send_report(report_def.id, recipients)
                
                processed += 1
                logger.info(
                    "scheduled_report_completed",
                    report_id=report_def.id,
                    next_run_at=next_run.isoformat() if next_run else None,
                )
                
            except Exception as exc:
                failed += 1
                logger.exception(
                    "scheduled_report_failed",
                    report_id=report_def.id,
                    error=str(exc),
                )
        
        # Commit all updates
        await session.commit()
        
        logger.info(
            "scheduled_reports_check_complete",
            processed=processed,
            failed=failed,
            checked=len(due_reports),
        )
        
        return {"processed": processed, "failed": failed, "checked": len(due_reports)}
        
    except Exception:
        logger.exception("scheduled_reports_check_failed")
        raise
    finally:
        if session:
            await session.close()


def _calculate_next_run(
    frequency: str | None,
    day_of_week: int | None,
    day_of_month: int | None,
    time_of_day: str,
    current_time: datetime,
) -> datetime | None:
    """
    Calculate the next run time based on schedule configuration.
    
    Args:
        frequency: Schedule frequency (daily, weekly, monthly, once)
        day_of_week: Day of week for weekly (0=Monday)
        day_of_month: Day of month for monthly (1-31)
        time_of_day: Time in HH:MM format
        current_time: Current datetime
        
    Returns:
        Next run datetime or None for one-time reports
    """
    if not frequency:
        return None
    
    # Parse time of day
    try:
        hour, minute = map(int, time_of_day.split(":"))
    except (ValueError, AttributeError):
        hour, minute = 0, 0
    
    if frequency == ScheduleFrequency.ONCE.value or frequency == "once":
        return None  # One-time reports don't have a next run
    
    elif frequency == ScheduleFrequency.DAILY.value or frequency == "daily":
        # Next day at specified time
        next_run = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= current_time:
            next_run += timedelta(days=1)
        return next_run
    
    elif frequency == ScheduleFrequency.WEEKLY.value or frequency == "weekly":
        # Next occurrence of specified day of week
        target_day = day_of_week if day_of_week is not None else 0
        days_ahead = target_day - current_time.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        next_run = current_time + timedelta(days=days_ahead)
        next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return next_run
    
    elif frequency == ScheduleFrequency.MONTHLY.value or frequency == "monthly":
        # Next occurrence of specified day of month
        target_day = day_of_month if day_of_month is not None else 1
        
        # Try this month first
        try:
            next_run = current_time.replace(day=target_day, hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            # Day doesn't exist in this month, go to next month
            next_run = None
        
        if next_run is None or next_run <= current_time:
            # Go to next month
            if current_time.month == 12:
                next_month = current_time.replace(year=current_time.year + 1, month=1, day=1)
            else:
                next_month = current_time.replace(month=current_time.month + 1, day=1)
            
            try:
                next_run = next_month.replace(day=target_day, hour=hour, minute=minute, second=0, microsecond=0)
            except ValueError:
                # Day doesn't exist in next month either, use last day
                if next_month.month == 12:
                    last_day = (next_month.replace(year=next_month.year + 1, month=1, day=1) - timedelta(days=1)).day
                else:
                    last_day = (next_month.replace(month=next_month.month + 1, day=1) - timedelta(days=1)).day
                next_run = next_month.replace(day=last_day, hour=hour, minute=minute, second=0, microsecond=0)
        
        return next_run
    
    return None
