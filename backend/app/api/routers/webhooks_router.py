"""Webhook API router."""
from __future__ import annotations

from typing import Annotated

import httpx
import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_roles, MANAGEMENT_ROLES
from app.infrastructure.db.session import get_session
from app.api.schemas.webhook import (
    WebhookDeliveryListOut,
    WebhookDeliveryOut,
    WebhookEventListOut,
    WebhookEventOut,
    WebhookEventTypes,
    WebhookSubscriptionCreate,
    WebhookSubscriptionListOut,
    WebhookSubscriptionOut,
    WebhookSubscriptionUpdate,
    WebhookSubscriptionWithSecretOut,
    WebhookTestRequest,
    WebhookTestResult,
)
from app.domain.common.errors import ConflictError, NotFoundError, ValidationError
from app.domain.webhooks import (
    WebhookDelivery,
    WebhookEvent,
    WebhookEventType,
    WebhookSubscription,
)
from app.infrastructure.db.repositories.webhook_repository import (
    SqlAlchemyWebhookDeliveryRepository,
    SqlAlchemyWebhookEventRepository,
    SqlAlchemyWebhookSubscriptionRepository,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _subscription_to_out(sub: WebhookSubscription) -> WebhookSubscriptionOut:
    """Convert subscription to output schema."""
    return WebhookSubscriptionOut(
        id=sub.id,
        name=sub.name,
        url=sub.url,
        events=[e.value for e in sub.events],
        status=sub.status.value,
        headers=sub.headers,
        description=sub.description,
        max_retries=sub.max_retries,
        retry_interval_seconds=sub.retry_interval_seconds,
        consecutive_failures=sub.consecutive_failures,
        last_failure_at=sub.last_failure_at,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        version=sub.version,
    )


@router.get("/event-types", response_model=WebhookEventTypes)
async def list_event_types(
    _: Annotated[None, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> WebhookEventTypes:
    """List all available webhook event types."""
    event_types = [
        {"value": e.value, "description": e.name.replace("_", " ").title()}
        for e in WebhookEventType
    ]
    return WebhookEventTypes(event_types=event_types)


@router.post(
    "/subscriptions",
    response_model=WebhookSubscriptionWithSecretOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    request: WebhookSubscriptionCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> WebhookSubscriptionWithSecretOut:
    """Create a new webhook subscription."""
    repo = SqlAlchemyWebhookSubscriptionRepository(session)

    # Check for duplicate name
    existing = await repo.get_by_name(request.name)
    if existing:
        raise ConflictError(
            f"Webhook subscription with name '{request.name}' already exists",
            code="webhook.duplicate_name",
        )

    # Validate event types
    try:
        events = [WebhookEventType(e) for e in request.events]
    except ValueError as e:
        raise ValidationError(
            f"Invalid event type: {e}",
            code="webhook.invalid_event_type",
        )

    subscription = WebhookSubscription.create(
        name=request.name,
        url=str(request.url),
        events=events,
        headers=request.headers,
        description=request.description,
        max_retries=request.max_retries,
        retry_interval_seconds=request.retry_interval_seconds,
    )

    await repo.add(subscription)

    return WebhookSubscriptionWithSecretOut(
        **_subscription_to_out(subscription).model_dump(),
        secret=subscription.secret,
    )


@router.get("/subscriptions", response_model=WebhookSubscriptionListOut)
async def list_subscriptions(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*MANAGEMENT_ROLES))],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WebhookSubscriptionListOut:
    """List all webhook subscriptions."""
    repo = SqlAlchemyWebhookSubscriptionRepository(session)
    offset = (page - 1) * limit
    subscriptions, total = await repo.list_all(offset=offset, limit=limit)

    return WebhookSubscriptionListOut(
        items=[_subscription_to_out(s) for s in subscriptions],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/subscriptions/{subscription_id}", response_model=WebhookSubscriptionOut)
async def get_subscription(
    subscription_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> WebhookSubscriptionOut:
    """Get a webhook subscription by ID."""
    repo = SqlAlchemyWebhookSubscriptionRepository(session)
    subscription = await repo.get_by_id(subscription_id)

    if not subscription:
        raise NotFoundError(
            f"Webhook subscription {subscription_id} not found",
            code="webhook.not_found",
        )

    return _subscription_to_out(subscription)


@router.patch("/subscriptions/{subscription_id}", response_model=WebhookSubscriptionOut)
async def update_subscription(
    subscription_id: str,
    request: WebhookSubscriptionUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> WebhookSubscriptionOut:
    """Update a webhook subscription."""
    repo = SqlAlchemyWebhookSubscriptionRepository(session)
    subscription = await repo.get_by_id(subscription_id)

    if not subscription:
        raise NotFoundError(
            f"Webhook subscription {subscription_id} not found",
            code="webhook.not_found",
        )

    old_version = subscription.version

    # Apply updates
    if request.name is not None:
        subscription.name = request.name
    if request.url is not None:
        subscription.url = str(request.url)
    if request.events is not None:
        try:
            subscription.events = [WebhookEventType(e) for e in request.events]
        except ValueError as e:
            raise ValidationError(
                f"Invalid event type: {e}",
                code="webhook.invalid_event_type",
            )
    if request.headers is not None:
        subscription.headers = request.headers
    if request.description is not None:
        subscription.description = request.description
    if request.max_retries is not None:
        subscription.max_retries = request.max_retries
    if request.retry_interval_seconds is not None:
        subscription.retry_interval_seconds = request.retry_interval_seconds

    subscription._touch()

    updated = await repo.update(subscription, expected_version=old_version)
    if not updated:
        raise ConflictError(
            "Subscription was modified by another request",
            code="webhook.version_conflict",
        )

    return _subscription_to_out(subscription)


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_subscription(
    subscription_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> None:
    """Delete a webhook subscription."""
    repo = SqlAlchemyWebhookSubscriptionRepository(session)
    deleted = await repo.delete(subscription_id)

    if not deleted:
        raise NotFoundError(
            f"Webhook subscription {subscription_id} not found",
            code="webhook.not_found",
        )


@router.post("/subscriptions/{subscription_id}/activate", response_model=WebhookSubscriptionOut)
async def activate_subscription(
    subscription_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> WebhookSubscriptionOut:
    """Activate a webhook subscription."""
    repo = SqlAlchemyWebhookSubscriptionRepository(session)
    subscription = await repo.get_by_id(subscription_id)

    if not subscription:
        raise NotFoundError(
            f"Webhook subscription {subscription_id} not found",
            code="webhook.not_found",
        )

    old_version = subscription.version
    subscription.activate()

    await repo.update(subscription, expected_version=old_version)
    return _subscription_to_out(subscription)


@router.post("/subscriptions/{subscription_id}/deactivate", response_model=WebhookSubscriptionOut)
async def deactivate_subscription(
    subscription_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> WebhookSubscriptionOut:
    """Deactivate a webhook subscription."""
    repo = SqlAlchemyWebhookSubscriptionRepository(session)
    subscription = await repo.get_by_id(subscription_id)

    if not subscription:
        raise NotFoundError(
            f"Webhook subscription {subscription_id} not found",
            code="webhook.not_found",
        )

    old_version = subscription.version
    subscription.deactivate()

    await repo.update(subscription, expected_version=old_version)
    return _subscription_to_out(subscription)


@router.post("/subscriptions/{subscription_id}/test", response_model=WebhookTestResult)
async def test_subscription(
    subscription_id: str,
    request: WebhookTestRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> WebhookTestResult:
    """Send a test webhook to verify endpoint."""
    repo = SqlAlchemyWebhookSubscriptionRepository(session)
    subscription = await repo.get_by_id(subscription_id)

    if not subscription:
        raise NotFoundError(
            f"Webhook subscription {subscription_id} not found",
            code="webhook.not_found",
        )

    # Validate event type
    try:
        event_type = WebhookEventType(request.event_type)
    except ValueError:
        raise ValidationError(
            f"Invalid event type: {request.event_type}",
            code="webhook.invalid_event_type",
        )

    # Create test event
    event = WebhookEvent.create(
        event_type=event_type,
        payload={"test": True, **request.payload},
        reference_id=None,
    )

    # Create delivery
    delivery = WebhookDelivery.create(subscription=subscription, event=event)

    # Send test request
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                delivery.url,
                content=delivery.request_body,
                headers=delivery.request_headers,
            )
        duration_ms = int((time.time() - start_time) * 1000)

        return WebhookTestResult(
            success=200 <= response.status_code < 300,
            status_code=response.status_code,
            response_body=response.text[:1000] if response.text else None,
            error_message=None,
            duration_ms=duration_ms,
        )
    except httpx.RequestError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return WebhookTestResult(
            success=False,
            status_code=None,
            response_body=None,
            error_message=str(e),
            duration_ms=duration_ms,
        )


@router.get("/subscriptions/{subscription_id}/deliveries", response_model=WebhookDeliveryListOut)
async def list_subscription_deliveries(
    subscription_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*MANAGEMENT_ROLES))],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> WebhookDeliveryListOut:
    """List deliveries for a webhook subscription."""
    repo = SqlAlchemyWebhookDeliveryRepository(session)
    offset = (page - 1) * limit

    from app.domain.webhooks import DeliveryStatus
    delivery_status = None
    if status_filter:
        try:
            delivery_status = DeliveryStatus(status_filter)
        except ValueError:
            raise ValidationError(
                f"Invalid status: {status_filter}",
                code="webhook.invalid_status",
            )

    deliveries, total = await repo.list_by_subscription(
        subscription_id,
        status=delivery_status,
        offset=offset,
        limit=limit,
    )

    return WebhookDeliveryListOut(
        items=[
            WebhookDeliveryOut(
                id=d.id,
                subscription_id=d.subscription_id,
                event_id=d.event_id,
                event_type=d.event_type.value,
                url=d.url,
                status=d.status.value,
                response_status_code=d.response_status_code,
                error_message=d.error_message,
                attempt_number=d.attempt_number,
                max_attempts=d.max_attempts,
                next_retry_at=d.next_retry_at,
                created_at=d.created_at,
                delivered_at=d.delivered_at,
                duration_ms=d.duration_ms,
            )
            for d in deliveries
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/events", response_model=WebhookEventListOut)
async def list_events(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[None, Depends(require_roles(*MANAGEMENT_ROLES))],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    event_type: Annotated[str | None, Query()] = None,
) -> WebhookEventListOut:
    """List recent webhook events."""
    repo = SqlAlchemyWebhookEventRepository(session)
    offset = (page - 1) * limit

    filter_type = None
    if event_type:
        try:
            filter_type = WebhookEventType(event_type)
        except ValueError:
            raise ValidationError(
                f"Invalid event type: {event_type}",
                code="webhook.invalid_event_type",
            )

    events, total = await repo.list_recent(
        event_type=filter_type,
        offset=offset,
        limit=limit,
    )

    return WebhookEventListOut(
        items=[
            WebhookEventOut(
                id=e.id,
                event_type=e.event_type.value,
                payload=e.payload,
                reference_id=e.reference_id,
                created_at=e.created_at,
            )
            for e in events
        ],
        total=total,
        page=page,
        limit=limit,
    )
