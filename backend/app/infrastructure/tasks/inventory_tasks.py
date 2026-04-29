from __future__ import annotations

"""Celery tasks for inventory intelligence routines.

Provides scheduled and on-demand tasks for:
- Inventory forecasting with exponential smoothing
- Low stock alert notifications
- Dead stock detection
- ABC classification updates
- Redis-cached forecast results
"""

import json
import structlog
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import redis

from app.application.inventory.use_cases.get_inventory_forecast import (
    GetInventoryForecastUseCase,
    InventoryForecastInput,
)
from app.application.inventory.use_cases.get_advanced_forecast import (
    GetAdvancedForecastUseCase,
    AdvancedForecastInput,
    ForecastConfidence,
)
from app.application.inventory.use_cases.get_inventory_insights import (
    GetInventoryInsightsUseCase,
)
from app.infrastructure.db.repositories.inventory_movement_repository import (
    SqlAlchemyInventoryMovementRepository,
)
from app.infrastructure.db.repositories.inventory_repository import SqlAlchemyProductRepository
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.product_import_tasks import AsyncTask
from app.infrastructure.websocket.event_dispatcher import get_event_dispatcher
from app.infrastructure.websocket.inventory_alerts import (
    broadcast_low_stock_alert,
    broadcast_out_of_stock_alert,
)
from app.core.settings import get_settings

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="refresh_inventory_forecast",
)
def refresh_inventory_forecast(
    self: AsyncTask,
    lookback_days: int = 60,
    lead_time_days: int = 7,
    safety_stock_days: int = 2,
    include_zero_demand: bool = False,
    ttl_minutes: int = 360,
) -> dict[str, object]:
    """Refresh inventory forecasts and return freshness metadata."""
    return self(*[lookback_days, lead_time_days, safety_stock_days, include_zero_demand, ttl_minutes])


@refresh_inventory_forecast.run_async  # type: ignore
async def refresh_inventory_forecast_async(
    lookback_days: int = 60,
    lead_time_days: int = 7,
    safety_stock_days: int = 2,
    include_zero_demand: bool = False,
    ttl_minutes: int = 360,
) -> dict[str, object]:
    logger.info(
        "refresh_inventory_forecast_started",
        lookback_days=lookback_days,
        lead_time_days=lead_time_days,
        safety_stock_days=safety_stock_days,
        include_zero_demand=include_zero_demand,
        ttl_minutes=ttl_minutes,
    )

    session: AsyncSession | None = None
    try:
        session = async_session_factory()
        product_repo = SqlAlchemyProductRepository(session)
        inventory_repo = SqlAlchemyInventoryMovementRepository(session)
        use_case = GetInventoryForecastUseCase(product_repo, inventory_repo)

        result = await use_case.execute(
            InventoryForecastInput(
                lookback_days=lookback_days,
                lead_time_days=lead_time_days,
                safety_stock_days=safety_stock_days,
                include_zero_demand=include_zero_demand,
                ttl_minutes=ttl_minutes,
            )
        )

        stale = datetime.now(UTC) >= result.expires_at

        payload = {
            "generated_at": result.generated_at.isoformat(),
            "expires_at": result.expires_at.isoformat(),
            "ttl_minutes": result.ttl_minutes,
            "forecasts": len(result.forecasts),
            "stale": stale,
        }
        logger.info("refresh_inventory_forecast_completed", **payload)
        return payload
    except Exception:
        logger.exception("refresh_inventory_forecast_failed")
        raise
    finally:
        if session:
            await session.close()


# ==================== Advanced Forecast Recomputation v2 ====================

# Redis cache keys
FORECAST_CACHE_KEY = "retail_pos:forecast:results"
FORECAST_CACHE_TTL = 28800  # 8 hours


def _get_redis_client() -> redis.Redis | None:
    """Get Redis client for caching, returns None if unavailable."""
    settings = get_settings()
    if not settings.CELERY_BROKER_URL:
        return None
    try:
        return redis.from_url(
            settings.CELERY_BROKER_URL,
            decode_responses=True,
            socket_timeout=5,
        )
    except Exception as e:
        logger.warning("redis_connection_failed", error=str(e))
        return None


def _cache_forecast_results(forecasts: list[dict], metadata: dict) -> bool:
    """Cache forecast results to Redis for fast retrieval."""
    client = _get_redis_client()
    if not client:
        return False
    
    try:
        cache_data = {
            "metadata": metadata,
            "forecasts": forecasts,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        client.setex(
            FORECAST_CACHE_KEY,
            FORECAST_CACHE_TTL,
            json.dumps(cache_data, default=str),
        )
        logger.info("forecast_cached_to_redis", forecast_count=len(forecasts))
        return True
    except Exception as e:
        logger.warning("forecast_cache_failed", error=str(e))
        return False


def get_cached_forecast() -> dict | None:
    """Retrieve cached forecast from Redis."""
    client = _get_redis_client()
    if not client:
        return None
    
    try:
        data = client.get(FORECAST_CACHE_KEY)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning("forecast_cache_read_failed", error=str(e))
        return None


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="recompute_forecast_model",
    max_retries=3,
    default_retry_delay=60,
)
def recompute_forecast_model(
    self: AsyncTask,
    smoothing_alpha: float = 0.3,
    seasonality: bool = True,
    lookback_days: int = 90,
    lead_time_days: int = 7,
    safety_stock_days: int = 3,
    broadcast_alerts: bool = True,
) -> dict[str, object]:
    """Recompute forecast model using advanced exponential smoothing.
    
    This task uses GetAdvancedForecastUseCase for:
    - Exponential smoothing with configurable alpha
    - Day-of-week seasonality detection
    - Confidence intervals (95%)
    - ABC classification integration
    
    Args:
        smoothing_alpha: Exponential smoothing factor (0.1-0.9). Lower = more history weight
        seasonality: Enable day-of-week seasonal adjustments
        lookback_days: Days of historical data to analyze (min 14 for seasonality)
        lead_time_days: Expected supplier lead time for reorder calculations
        safety_stock_days: Buffer stock days added to reorder point
        broadcast_alerts: Send WebSocket alerts for critical forecasts
    
    Returns:
        Dict with forecast metadata and summary statistics
    """
    return self(
        *[smoothing_alpha, seasonality, lookback_days, lead_time_days, safety_stock_days, broadcast_alerts]
    )


@recompute_forecast_model.run_async  # type: ignore
async def recompute_forecast_model_async(
    smoothing_alpha: float = 0.3,
    seasonality: bool = True,
    lookback_days: int = 90,
    lead_time_days: int = 7,
    safety_stock_days: int = 3,
    broadcast_alerts: bool = True,
) -> dict[str, object]:
    """Advanced forecast model recomputation with full exponential smoothing."""
    logger.info(
        "recompute_forecast_model_v2_started",
        smoothing_alpha=smoothing_alpha,
        seasonality=seasonality,
        lookback_days=lookback_days,
        lead_time_days=lead_time_days,
        broadcast_alerts=broadcast_alerts,
    )

    session: AsyncSession | None = None
    try:
        session = async_session_factory()
        product_repo = SqlAlchemyProductRepository(session)
        inventory_repo = SqlAlchemyInventoryMovementRepository(session)
        
        # Use Advanced Forecast Use Case with proper exponential smoothing
        use_case = GetAdvancedForecastUseCase(product_repo, inventory_repo)
        
        result = await use_case.execute(
            AdvancedForecastInput(
                lookback_days=lookback_days,
                lead_time_days=lead_time_days,
                safety_stock_days=safety_stock_days,
                include_zero_demand=False,
                ttl_minutes=480,  # 8 hours for recomputed model
                smoothing_alpha=Decimal(str(smoothing_alpha)),
                use_seasonality=seasonality,
                min_data_points=14 if seasonality else 7,
            )
        )
        
        # Build serializable forecast results
        forecasts_data = []
        critical_forecasts = []
        
        for fc in result.forecasts:
            forecast_entry = {
                "product_id": fc.product.id,
                "name": fc.product.name,
                "sku": fc.product.sku,
                "quantity_on_hand": fc.stock.quantity_on_hand,
                "daily_demand": float(fc.daily_demand),
                "daily_demand_smoothed": float(fc.daily_demand_smoothed),
                "days_until_stockout": fc.days_until_stockout,
                "stockout_best_case": fc.stockout_best_case_days,
                "stockout_worst_case": fc.stockout_worst_case_days,
                "recommended_order": fc.recommended_order,
                "confidence": fc.confidence.value,
                "coefficient_of_variation": float(fc.coefficient_of_variation),
                "forecast_method": fc.forecast_method.value,
                "projected_stockout_date": fc.projected_stockout_date.isoformat() if fc.projected_stockout_date.year < 9999 else None,
                "recommended_reorder_date": fc.recommended_reorder_date.isoformat() if fc.recommended_reorder_date.year < 9999 else None,
            }
            
            # Add seasonality if available
            if fc.seasonality_factors:
                forecast_entry["seasonality"] = {
                    "monday": float(fc.seasonality_factors.monday),
                    "tuesday": float(fc.seasonality_factors.tuesday),
                    "wednesday": float(fc.seasonality_factors.wednesday),
                    "thursday": float(fc.seasonality_factors.thursday),
                    "friday": float(fc.seasonality_factors.friday),
                    "saturday": float(fc.seasonality_factors.saturday),
                    "sunday": float(fc.seasonality_factors.sunday),
                }
            
            forecasts_data.append(forecast_entry)
            
            # Collect critical items (stockout within lead time)
            if fc.days_until_stockout <= lead_time_days:
                critical_forecasts.append(forecast_entry)
        
        # Cache results to Redis
        metadata = {
            "generated_at": result.generated_at.isoformat(),
            "expires_at": result.expires_at.isoformat(),
            "ttl_minutes": result.ttl_minutes,
            "lookback_days": result.lookback_days,
            "lead_time_days": result.lead_time_days,
            "safety_stock_days": result.safety_stock_days,
            "smoothing_alpha": float(result.smoothing_alpha),
            "seasonality_enabled": result.use_seasonality,
            "total_products": result.total_products_analyzed,
            "high_confidence": result.high_confidence_count,
            "medium_confidence": result.medium_confidence_count,
            "low_confidence": result.low_confidence_count,
        }
        
        cached = _cache_forecast_results(forecasts_data, metadata)
        
        # Broadcast WebSocket alerts for critical items
        ws_alerts_sent = 0
        if broadcast_alerts and critical_forecasts:
            try:
                from app.infrastructure.websocket.handlers.inventory_handler import InventoryEventHandler
                
                for fc in critical_forecasts[:10]:  # Limit to top 10 critical
                    await InventoryEventHandler.publish_reorder_alert(
                        product_id=fc["product_id"],
                        product_name=fc["name"],
                        sku=fc["sku"],
                        current_quantity=Decimal(str(fc["quantity_on_hand"])),
                        reorder_point=Decimal(str(fc["recommended_order"])),
                        suggested_order_qty=Decimal(str(fc["recommended_order"])),
                        days_until_stockout=int(fc["days_until_stockout"]) if fc["days_until_stockout"] != float("inf") else 999,
                        tenant_id="default",
                    )
                    ws_alerts_sent += 1
                        
            except Exception as ws_error:
                logger.warning("forecast_ws_alert_failed", error=str(ws_error))
        
        payload = {
            "generated_at": result.generated_at.isoformat(),
            "expires_at": result.expires_at.isoformat(),
            "ttl_minutes": result.ttl_minutes,
            "forecast_count": len(result.forecasts),
            "smoothing_alpha": smoothing_alpha,
            "seasonality_enabled": seasonality,
            "high_confidence_count": result.high_confidence_count,
            "medium_confidence_count": result.medium_confidence_count,
            "low_confidence_count": result.low_confidence_count,
            "critical_items": len(critical_forecasts),
            "ws_alerts_sent": ws_alerts_sent,
            "cached": cached,
            "stale": False,
        }
        
        logger.info("recompute_forecast_model_v2_completed", **payload)
        return payload
        
    except Exception as exc:
        logger.exception("recompute_forecast_model_v2_failed")
        raise
    finally:
        if session:
            await session.close()


# ==================== Low Stock Alert Notifications ====================

# Alert throttling cache (in production, use Redis)
_last_alert_times: dict[str, datetime] = {}
ALERT_THROTTLE_HOURS = 4  # Don't re-alert same item within 4 hours


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="check_low_stock_alerts",
)
def check_low_stock_alerts(
    self: AsyncTask,
    threshold_days: int = 7,
    email_recipients: list[str] | None = None,
    enable_sms: bool = False,
) -> dict[str, object]:
    """Check for low stock items and send alerts.
    
    Args:
        threshold_days: Alert if days_until_stockout <= threshold
        email_recipients: List of email addresses to notify
        enable_sms: Enable SMS notifications (requires SMS provider)
    """
    return self(*[threshold_days, email_recipients or [], enable_sms])


@check_low_stock_alerts.run_async  # type: ignore
async def check_low_stock_alerts_async(
    threshold_days: int = 7,
    email_recipients: list[str] | None = None,
    enable_sms: bool = False,
) -> dict[str, object]:
    """Check low stock and dispatch notifications."""
    logger.info(
        "check_low_stock_alerts_started",
        threshold_days=threshold_days,
        recipient_count=len(email_recipients or []),
        sms_enabled=enable_sms,
    )

    session: AsyncSession | None = None
    alerts_sent = 0
    throttled = 0
    
    try:
        session = async_session_factory()
        product_repo = SqlAlchemyProductRepository(session)
        inventory_repo = SqlAlchemyInventoryMovementRepository(session)
        
        # Get inventory insights with low stock
        insights_use_case = GetInventoryInsightsUseCase(product_repo, inventory_repo)
        insights = await insights_use_case.execute()
        
        low_stock_items = insights.low_stock
        
        if not low_stock_items:
            logger.info("check_low_stock_alerts_no_alerts")
            return {
                "alerts_sent": 0,
                "throttled": 0,
                "low_stock_count": 0,
            }
        
        # Filter by threshold and throttle
        now = datetime.now(UTC)
        items_to_alert = []
        
        for item in low_stock_items:
            product_key = f"low_stock_{item.product_id}"
            last_alert = _last_alert_times.get(product_key)
            
            if last_alert and (now - last_alert) < timedelta(hours=ALERT_THROTTLE_HOURS):
                throttled += 1
                continue
                
            items_to_alert.append(item)
            _last_alert_times[product_key] = now
        
        if not items_to_alert:
            logger.info("check_low_stock_alerts_all_throttled", throttled=throttled)
            return {
                "alerts_sent": 0,
                "throttled": throttled,
                "low_stock_count": len(low_stock_items),
            }
        
        # Send email alerts
        if email_recipients:
            from app.infrastructure.tasks.email_tasks import send_email
            
            # Build email content
            subject = f"🚨 Low Stock Alert: {len(items_to_alert)} items need attention"
            
            items_html = ""
            for item in items_to_alert[:20]:  # Limit to 20 in email
                items_html += f"""
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;">{item.name}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{item.sku}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; color: red;">{item.quantity_on_hand}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{item.reorder_point}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; color: green;">{item.recommended_order}</td>
                </tr>
                """
            
            body_html = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #e53935;">⚠️ Low Stock Alert</h2>
                <p>{len(items_to_alert)} product(s) have fallen below reorder levels and require attention.</p>
                
                <table style="border-collapse: collapse; width: 100%; margin-top: 20px;">
                    <thead>
                        <tr style="background-color: #f5f5f5;">
                            <th style="padding: 10px; border: 1px solid #ddd;">Product</th>
                            <th style="padding: 10px; border: 1px solid #ddd;">SKU</th>
                            <th style="padding: 10px; border: 1px solid #ddd;">On Hand</th>
                            <th style="padding: 10px; border: 1px solid #ddd;">Reorder Point</th>
                            <th style="padding: 10px; border: 1px solid #ddd;">Recommended Order</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>
                
                <p style="margin-top: 20px; color: #666;">
                    This alert was generated automatically by Retail POS Inventory Intelligence.
                </p>
            </body>
            </html>
            """
            
            for recipient in email_recipients:
                try:
                    send_email.delay(
                        to_email=recipient,
                        subject=subject,
                        body_text=f"Low Stock Alert: {len(items_to_alert)} items need attention. Check inventory dashboard for details.",
                        body_html=body_html,
                    )
                    alerts_sent += 1
                except Exception as e:
                    logger.warning("email_send_failed", recipient=recipient, error=str(e))
        
        # SMS alerts (stub for future SMS provider integration)
        if enable_sms and items_to_alert:
            # Would integrate with Twilio, AWS SNS, or similar
            logger.info(
                "sms_alerts_would_send",
                count=len(items_to_alert),
                message="SMS integration not configured",
            )
        
        # Broadcast WebSocket alerts for real-time UI updates
        websocket_broadcasts = 0
        try:
            dispatcher = get_event_dispatcher()
            if dispatcher:
                for item in items_to_alert:
                    # Get tenant_id from item or use default
                    tenant_id = getattr(item, "tenant_id", None) or "default"
                    quantity = getattr(item, "quantity_on_hand", Decimal("0"))
                    
                    if quantity <= 0:
                        # Out of stock
                        await broadcast_out_of_stock_alert(
                            dispatcher=dispatcher,
                            tenant_id=tenant_id,
                            product_id=item.product_id,
                            product_name=item.name,
                            sku=item.sku,
                        )
                    else:
                        # Low stock
                        await broadcast_low_stock_alert(
                            dispatcher=dispatcher,
                            tenant_id=tenant_id,
                            product_id=item.product_id,
                            product_name=item.name,
                            sku=item.sku,
                            current_quantity=quantity,
                            reorder_point=getattr(item, "reorder_point", Decimal("0")),
                            days_until_stockout=getattr(item, "days_until_stockout", None),
                            recommended_order=getattr(item, "recommended_order", None),
                        )
                    websocket_broadcasts += 1
                    
                logger.info(
                    "low_stock_websocket_broadcasts_sent",
                    count=websocket_broadcasts,
                )
        except Exception as ws_error:
            logger.warning(
                "websocket_broadcast_failed",
                error=str(ws_error),
            )
        
        payload = {
            "alerts_sent": alerts_sent,
            "throttled": throttled,
            "low_stock_count": len(low_stock_items),
            "items_alerted": len(items_to_alert),
            "websocket_broadcasts": websocket_broadcasts,
        }
        
        logger.info("check_low_stock_alerts_completed", **payload)
        return payload
        
    except Exception:
        logger.exception("check_low_stock_alerts_failed")
        raise
    finally:
        if session:
            await session.close()


# ==================== Dead Stock Notification ====================

@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="check_dead_stock_alerts",
)
def check_dead_stock_alerts(
    self: AsyncTask,
    days_inactive: int = 90,
    email_recipients: list[str] | None = None,
) -> dict[str, object]:
    """Check for dead stock (no movement for X days) and notify."""
    return self(*[days_inactive, email_recipients or []])


@check_dead_stock_alerts.run_async  # type: ignore
async def check_dead_stock_alerts_async(
    days_inactive: int = 90,
    email_recipients: list[str] | None = None,
) -> dict[str, object]:
    """Check for dead stock and send weekly summary."""
    logger.info(
        "check_dead_stock_alerts_started",
        days_inactive=days_inactive,
    )

    session: AsyncSession | None = None
    
    try:
        session = async_session_factory()
        product_repo = SqlAlchemyProductRepository(session)
        inventory_repo = SqlAlchemyInventoryMovementRepository(session)
        
        insights_use_case = GetInventoryInsightsUseCase(product_repo, inventory_repo)
        insights = await insights_use_case.execute()
        
        dead_stock_items = [
            item for item in insights.dead_stock
            if item.days_since_movement >= days_inactive
        ]
        
        if not dead_stock_items:
            logger.info("check_dead_stock_alerts_no_items")
            return {"dead_stock_count": 0, "alerts_sent": 0}
        
        # Send summary email
        alerts_sent = 0
        if email_recipients:
            from app.infrastructure.tasks.email_tasks import send_email
            
            subject = f"📦 Dead Stock Report: {len(dead_stock_items)} items with no movement"
            
            items_html = ""
            for item in dead_stock_items[:30]:
                items_html += f"""
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;">{item.name}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{item.sku}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{item.quantity_on_hand}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{item.days_since_movement} days</td>
                </tr>
                """
            
            body_html = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #ff9800;">📦 Dead Stock Report</h2>
                <p>{len(dead_stock_items)} product(s) have had no movement for {days_inactive}+ days.</p>
                <p>Consider discounting, bundling, or removing these items from inventory.</p>
                
                <table style="border-collapse: collapse; width: 100%; margin-top: 20px;">
                    <thead>
                        <tr style="background-color: #f5f5f5;">
                            <th style="padding: 10px; border: 1px solid #ddd;">Product</th>
                            <th style="padding: 10px; border: 1px solid #ddd;">SKU</th>
                            <th style="padding: 10px; border: 1px solid #ddd;">Qty On Hand</th>
                            <th style="padding: 10px; border: 1px solid #ddd;">Days Inactive</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>
            </body>
            </html>
            """
            
            for recipient in email_recipients:
                try:
                    send_email.delay(
                        to_email=recipient,
                        subject=subject,
                        body_text=f"Dead Stock Report: {len(dead_stock_items)} items with no movement for {days_inactive}+ days.",
                        body_html=body_html,
                    )
                    alerts_sent += 1
                except Exception as e:
                    logger.warning("dead_stock_email_failed", recipient=recipient, error=str(e))
        
        return {
            "dead_stock_count": len(dead_stock_items),
            "alerts_sent": alerts_sent,
        }
        
    except Exception:
        logger.exception("check_dead_stock_alerts_failed")
        raise
    finally:
        if session:
            await session.close()
