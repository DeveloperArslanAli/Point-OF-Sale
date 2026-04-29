"""
Webhook dispatch and delivery tasks.

This module handles asynchronous webhook delivery with retry logic,
including both immediate dispatch and scheduled retry processing.
"""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import structlog

from app.domain.webhooks.entities import DeliveryStatus, WebhookEvent, WebhookEventType
from app.infrastructure.tasks.celery_app import celery_app

if TYPE_CHECKING:
    from celery import Task

logger = structlog.get_logger(__name__)

# Webhook delivery configuration
WEBHOOK_TIMEOUT_SECONDS = 30
WEBHOOK_MAX_RESPONSE_SIZE = 10_000  # 10KB max response body to store


def _run_async(coro):
    """Run an async coroutine in the event loop.
    
    Handles the case where we may be in a context with an existing loop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # We're in an async context, create a new loop in a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


@celery_app.task(
    bind=True,
    name="dispatch_webhook_event",
    queue="webhooks",
    max_retries=0,  # We handle retries ourselves
    soft_time_limit=60,
    time_limit=90,
)
def dispatch_webhook_event(
    self: Task,
    event_id: str,
    event_type: str,
    payload: dict,
    reference_id: str | None = None,
    tenant_id: str | None = None,
) -> dict:
    """
    Dispatch a webhook event to all subscribed endpoints.
    
    This task:
    1. Creates a WebhookEvent record
    2. Finds all active subscriptions for this event type
    3. Creates WebhookDelivery records for each
    4. Attempts immediate delivery
    5. Schedules retries for failures
    
    Args:
        event_id: Unique event identifier
        event_type: Type of event (e.g., "sale.created")
        payload: Event payload data
        reference_id: Optional related entity ID
        tenant_id: Tenant context for multi-tenant isolation
    
    Returns:
        Summary of dispatch results
    """
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.db.repositories.webhook_repository import (
        SqlAlchemyWebhookRepository,
    )
    from app.domain.webhooks.entities import (
        WebhookEvent,
        WebhookDelivery,
        WebhookEventType,
    )
    
    log = logger.bind(
        task_id=self.request.id,
        event_id=event_id,
        event_type=event_type,
        reference_id=reference_id,
        tenant_id=tenant_id,
    )
    log.info("webhook_dispatch_started")
    
    async def _dispatch() -> dict:
        async with async_session_factory() as session:
            repo = SqlAlchemyWebhookRepository(session)
            
            # Get event type enum
            try:
                event_type_enum = WebhookEventType(event_type)
            except ValueError:
                log.warning("unknown_event_type", event_type=event_type)
                return {"status": "error", "message": f"Unknown event type: {event_type}"}
            
            # Create the event record
            event = WebhookEvent.create(
                event_type=event_type_enum,
                payload=payload,
                reference_id=reference_id,
            )
            # Override ID if provided
            if event_id:
                object.__setattr__(event, "id", event_id)
            
            await repo.save_event(event, tenant_id=tenant_id)
            
            # Find subscribed webhooks
            subscriptions = await repo.get_active_subscriptions_for_event(
                event_type_enum,
                tenant_id=tenant_id,
            )
            
            if not subscriptions:
                log.info("no_subscriptions_found")
                return {"status": "ok", "deliveries": 0, "message": "No subscriptions"}
            
            log.info("found_subscriptions", count=len(subscriptions))
            
            results = {
                "status": "ok",
                "deliveries": len(subscriptions),
                "success": 0,
                "failed": 0,
                "retrying": 0,
            }
            
            # Create and attempt delivery for each subscription
            for subscription in subscriptions:
                delivery = WebhookDelivery.create(
                    subscription=subscription,
                    event=event,
                )
                
                # Attempt delivery
                delivery_result = await _attempt_delivery(delivery, log)
                
                # Update subscription status based on result
                if delivery_result["success"]:
                    subscription.record_success()
                    results["success"] += 1
                else:
                    subscription.record_failure()
                    if delivery.status == DeliveryStatus.RETRYING:
                        results["retrying"] += 1
                    else:
                        results["failed"] += 1
                
                # Save delivery and updated subscription
                await repo.save_delivery(delivery, tenant_id=tenant_id)
                await repo.update_subscription(subscription)
            
            await session.commit()
            
            log.info(
                "webhook_dispatch_completed",
                success=results["success"],
                failed=results["failed"],
                retrying=results["retrying"],
            )
            
            return results
    
    return _run_async(_dispatch())


async def _attempt_delivery(
    delivery: "WebhookDelivery",
    log: structlog.BoundLogger,
) -> dict:
    """
    Attempt to deliver a webhook to its target URL.
    
    Returns:
        Dict with success boolean and optional error message
    """
    from app.domain.webhooks.entities import WebhookDelivery
    
    start_time = time.monotonic()
    
    log = log.bind(
        delivery_id=delivery.id,
        url=delivery.url,
        attempt=delivery.attempt_number,
    )
    
    try:
        async with httpx.AsyncClient(
            timeout=WEBHOOK_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = await client.post(
                delivery.url,
                content=delivery.request_body,
                headers=delivery.request_headers,
            )
        
        duration_ms = int((time.monotonic() - start_time) * 1000)
        response_body = response.text[:WEBHOOK_MAX_RESPONSE_SIZE]
        
        # Success if 2xx status code
        if 200 <= response.status_code < 300:
            delivery.mark_success(
                status_code=response.status_code,
                response_body=response_body,
                duration_ms=duration_ms,
            )
            log.info(
                "webhook_delivery_success",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            return {"success": True}
        else:
            delivery.mark_failed(
                status_code=response.status_code,
                response_body=response_body,
                error_message=f"HTTP {response.status_code}",
                duration_ms=duration_ms,
            )
            log.warning(
                "webhook_delivery_http_error",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            return {"success": False, "error": f"HTTP {response.status_code}"}
    
    except httpx.TimeoutException as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        delivery.mark_failed(
            error_message=f"Timeout after {WEBHOOK_TIMEOUT_SECONDS}s",
            duration_ms=duration_ms,
        )
        log.warning("webhook_delivery_timeout", duration_ms=duration_ms)
        return {"success": False, "error": "timeout"}
    
    except httpx.RequestError as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        delivery.mark_failed(
            error_message=str(e),
            duration_ms=duration_ms,
        )
        log.warning("webhook_delivery_error", error=str(e), duration_ms=duration_ms)
        return {"success": False, "error": str(e)}


@celery_app.task(
    bind=True,
    name="retry_failed_webhooks",
    queue="webhooks",
    soft_time_limit=300,
    time_limit=360,
)
def retry_failed_webhooks(self: Task, tenant_id: str | None = None) -> dict:
    """
    Retry failed webhook deliveries that are due for retry.
    
    This task is scheduled to run periodically (e.g., every minute) to:
    1. Find deliveries with status=RETRYING and next_retry_at <= now
    2. Attempt redelivery
    3. Update status accordingly
    
    Returns:
        Summary of retry results
    """
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.db.repositories.webhook_repository import (
        SqlAlchemyWebhookRepository,
    )
    
    log = logger.bind(task_id=self.request.id, tenant_id=tenant_id)
    log.info("retry_failed_webhooks_started")
    
    async def _retry() -> dict:
        async with async_session_factory() as session:
            repo = SqlAlchemyWebhookRepository(session)
            
            # Get pending retries
            deliveries = await repo.get_pending_retries(
                before=datetime.now(UTC),
                limit=100,
                tenant_id=tenant_id,
            )
            
            if not deliveries:
                log.info("no_pending_retries")
                return {"status": "ok", "retried": 0}
            
            log.info("found_pending_retries", count=len(deliveries))
            
            results = {"status": "ok", "retried": len(deliveries), "success": 0, "failed": 0}
            
            for delivery in deliveries:
                # Get subscription for this delivery
                subscription = await repo.get_subscription_by_id(delivery.subscription_id)
                if not subscription:
                    log.warning(
                        "subscription_not_found",
                        subscription_id=delivery.subscription_id,
                    )
                    delivery.status = DeliveryStatus.FAILED
                    delivery.error_message = "Subscription not found"
                    await repo.update_delivery(delivery)
                    results["failed"] += 1
                    continue
                
                # Increment attempt counter
                delivery.increment_attempt()
                
                # Attempt delivery
                result = await _attempt_delivery(delivery, log)
                
                if result["success"]:
                    subscription.record_success()
                    results["success"] += 1
                else:
                    subscription.record_failure()
                    results["failed"] += 1
                
                await repo.update_delivery(delivery)
                await repo.update_subscription(subscription)
            
            await session.commit()
            
            log.info(
                "retry_failed_webhooks_completed",
                success=results["success"],
                failed=results["failed"],
            )
            
            return results
    
    return _run_async(_retry())


@celery_app.task(
    bind=True,
    name="cleanup_old_webhook_deliveries",
    queue="default",
    soft_time_limit=300,
    time_limit=360,
)
def cleanup_old_webhook_deliveries(
    self: Task,
    retention_days: int = 30,
    tenant_id: str | None = None,
) -> dict:
    """
    Clean up old webhook delivery records.
    
    Args:
        retention_days: Delete deliveries older than this many days
        tenant_id: Optional tenant filter
    
    Returns:
        Summary of cleanup results
    """
    import asyncio
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.db.repositories.webhook_repository import (
        SqlAlchemyWebhookRepository,
    )
    
    log = logger.bind(
        task_id=self.request.id,
        retention_days=retention_days,
        tenant_id=tenant_id,
    )
    log.info("cleanup_webhook_deliveries_started")
    
    async def _cleanup() -> dict:
        async with async_session_factory() as session:
            repo = SqlAlchemyWebhookRepository(session)
            
            cutoff = datetime.now(UTC) - timedelta(days=retention_days)
            deleted_count = await repo.delete_deliveries_before(
                cutoff,
                tenant_id=tenant_id,
            )
            
            await session.commit()
            
            log.info(
                "cleanup_webhook_deliveries_completed",
                deleted_count=deleted_count,
            )
            
            return {"status": "ok", "deleted": deleted_count}
    
    return _run_async(_cleanup())
