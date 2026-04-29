"""SQLAlchemy repository for webhook system."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import get_current_tenant_id
from app.domain.webhooks import (
    DeliveryStatus,
    WebhookDelivery,
    WebhookEvent,
    WebhookEventType,
    WebhookStatus,
    WebhookSubscription,
)
from app.infrastructure.db.models.webhook_model import (
    WebhookDeliveryModel,
    WebhookEventModel,
    WebhookSubscriptionModel,
)


class SqlAlchemyWebhookSubscriptionRepository:
    """SQLAlchemy implementation of webhook subscription repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(WebhookSubscriptionModel.tenant_id == tenant_id)
        return stmt

    def _to_domain(self, model: WebhookSubscriptionModel) -> WebhookSubscription:
        """Convert model to domain entity."""
        return WebhookSubscription(
            id=model.id,
            name=model.name,
            url=model.url,
            secret=model.secret,
            events=[WebhookEventType(e) for e in model.events],
            status=WebhookStatus(model.status.value if hasattr(model.status, 'value') else model.status),
            headers=model.headers_json or {},
            description=model.description,
            max_retries=model.max_retries,
            retry_interval_seconds=model.retry_interval_seconds,
            consecutive_failures=model.consecutive_failures,
            failure_threshold=model.failure_threshold,
            last_failure_at=model.last_failure_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, entity: WebhookSubscription) -> WebhookSubscriptionModel:
        """Convert domain entity to model."""
        return WebhookSubscriptionModel(
            id=entity.id,
            name=entity.name,
            url=entity.url,
            secret=entity.secret,
            events=[e.value for e in entity.events],
            status=entity.status,
            headers_json=entity.headers,
            description=entity.description,
            max_retries=entity.max_retries,
            retry_interval_seconds=entity.retry_interval_seconds,
            consecutive_failures=entity.consecutive_failures,
            failure_threshold=entity.failure_threshold,
            last_failure_at=entity.last_failure_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            version=entity.version,
            tenant_id=get_current_tenant_id(),
        )

    async def add(self, subscription: WebhookSubscription) -> None:
        """Add a new webhook subscription."""
        model = self._to_model(subscription)
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, subscription_id: str) -> WebhookSubscription | None:
        """Get subscription by ID."""
        stmt = select(WebhookSubscriptionModel).where(
            WebhookSubscriptionModel.id == subscription_id
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_name(self, name: str) -> WebhookSubscription | None:
        """Get subscription by name."""
        stmt = select(WebhookSubscriptionModel).where(
            WebhookSubscriptionModel.name == name
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def update(
        self, subscription: WebhookSubscription, *, expected_version: int
    ) -> bool:
        """Update subscription with optimistic locking."""
        stmt = select(WebhookSubscriptionModel).where(
            WebhookSubscriptionModel.id == subscription.id,
            WebhookSubscriptionModel.version == expected_version,
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return False

        model.name = subscription.name
        model.url = subscription.url
        model.secret = subscription.secret
        model.events = [e.value for e in subscription.events]
        model.status = subscription.status
        model.headers_json = subscription.headers
        model.description = subscription.description
        model.max_retries = subscription.max_retries
        model.retry_interval_seconds = subscription.retry_interval_seconds
        model.consecutive_failures = subscription.consecutive_failures
        model.failure_threshold = subscription.failure_threshold
        model.last_failure_at = subscription.last_failure_at
        model.updated_at = subscription.updated_at
        model.version = subscription.version

        await self._session.flush()
        return True

    async def delete(self, subscription_id: str) -> bool:
        """Delete a subscription."""
        stmt = delete(WebhookSubscriptionModel).where(
            WebhookSubscriptionModel.id == subscription_id
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def list_by_event(
        self, event_type: WebhookEventType
    ) -> Sequence[WebhookSubscription]:
        """List active subscriptions for an event type."""
        stmt = select(WebhookSubscriptionModel).where(
            WebhookSubscriptionModel.status == WebhookStatus.ACTIVE,
            WebhookSubscriptionModel.events.contains([event_type.value]),
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[WebhookSubscription], int]:
        """List all subscriptions."""
        base_stmt = select(WebhookSubscriptionModel)
        base_stmt = self._apply_tenant_filter(base_stmt)

        # Count query
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Data query
        stmt = base_stmt.offset(offset).limit(limit).order_by(
            WebhookSubscriptionModel.created_at.desc()
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(m) for m in models], total


class SqlAlchemyWebhookEventRepository:
    """SQLAlchemy implementation of webhook event repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(WebhookEventModel.tenant_id == tenant_id)
        return stmt

    def _to_domain(self, model: WebhookEventModel) -> WebhookEvent:
        """Convert model to domain entity."""
        return WebhookEvent(
            id=model.id,
            event_type=WebhookEventType(
                model.event_type.value
                if hasattr(model.event_type, 'value')
                else model.event_type
            ),
            payload=model.payload_json,
            reference_id=model.reference_id,
            created_at=model.created_at,
        )

    def _to_model(self, entity: WebhookEvent) -> WebhookEventModel:
        """Convert domain entity to model."""
        return WebhookEventModel(
            id=entity.id,
            event_type=entity.event_type,
            payload_json=entity.payload,
            reference_id=entity.reference_id,
            created_at=entity.created_at,
            tenant_id=get_current_tenant_id(),
        )

    async def add(self, event: WebhookEvent) -> None:
        """Add a new webhook event."""
        model = self._to_model(event)
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, event_id: str) -> WebhookEvent | None:
        """Get event by ID."""
        stmt = select(WebhookEventModel).where(WebhookEventModel.id == event_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_recent(
        self,
        *,
        event_type: WebhookEventType | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[WebhookEvent], int]:
        """List recent events."""
        base_stmt = select(WebhookEventModel)
        if event_type:
            base_stmt = base_stmt.where(WebhookEventModel.event_type == event_type)
        base_stmt = self._apply_tenant_filter(base_stmt)

        # Count query
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Data query
        stmt = base_stmt.offset(offset).limit(limit).order_by(
            WebhookEventModel.created_at.desc()
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(m) for m in models], total


class SqlAlchemyWebhookDeliveryRepository:
    """SQLAlchemy implementation of webhook delivery repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(WebhookDeliveryModel.tenant_id == tenant_id)
        return stmt

    def _to_domain(self, model: WebhookDeliveryModel) -> WebhookDelivery:
        """Convert model to domain entity."""
        return WebhookDelivery(
            id=model.id,
            subscription_id=model.subscription_id,
            event_id=model.event_id,
            event_type=WebhookEventType(
                model.event_type.value
                if hasattr(model.event_type, 'value')
                else model.event_type
            ),
            url=model.url,
            status=DeliveryStatus(
                model.status.value if hasattr(model.status, 'value') else model.status
            ),
            request_headers=model.request_headers_json or {},
            request_body=model.request_body,
            response_status_code=model.response_status_code,
            response_body=model.response_body,
            error_message=model.error_message,
            attempt_number=model.attempt_number,
            max_attempts=model.max_attempts,
            next_retry_at=model.next_retry_at,
            created_at=model.created_at,
            delivered_at=model.delivered_at,
            duration_ms=model.duration_ms,
        )

    def _to_model(self, entity: WebhookDelivery) -> WebhookDeliveryModel:
        """Convert domain entity to model."""
        return WebhookDeliveryModel(
            id=entity.id,
            subscription_id=entity.subscription_id,
            event_id=entity.event_id,
            event_type=entity.event_type,
            url=entity.url,
            status=entity.status,
            request_headers_json=entity.request_headers,
            request_body=entity.request_body,
            response_status_code=entity.response_status_code,
            response_body=entity.response_body,
            error_message=entity.error_message,
            attempt_number=entity.attempt_number,
            max_attempts=entity.max_attempts,
            next_retry_at=entity.next_retry_at,
            created_at=entity.created_at,
            delivered_at=entity.delivered_at,
            duration_ms=entity.duration_ms,
            tenant_id=get_current_tenant_id(),
        )

    async def add(self, delivery: WebhookDelivery) -> None:
        """Add a new delivery record."""
        model = self._to_model(delivery)
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, delivery_id: str) -> WebhookDelivery | None:
        """Get delivery by ID."""
        stmt = select(WebhookDeliveryModel).where(
            WebhookDeliveryModel.id == delivery_id
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def update(self, delivery: WebhookDelivery) -> None:
        """Update a delivery record."""
        stmt = select(WebhookDeliveryModel).where(
            WebhookDeliveryModel.id == delivery.id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            model.status = delivery.status
            model.response_status_code = delivery.response_status_code
            model.response_body = delivery.response_body
            model.error_message = delivery.error_message
            model.attempt_number = delivery.attempt_number
            model.next_retry_at = delivery.next_retry_at
            model.delivered_at = delivery.delivered_at
            model.duration_ms = delivery.duration_ms
            await self._session.flush()

    async def list_pending_retries(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[WebhookDelivery]:
        """List deliveries pending retry."""
        now = datetime.now(UTC)
        stmt = select(WebhookDeliveryModel).where(
            WebhookDeliveryModel.status == DeliveryStatus.RETRYING,
            WebhookDeliveryModel.next_retry_at <= now,
        )
        stmt = self._apply_tenant_filter(stmt)
        stmt = stmt.limit(limit).order_by(WebhookDeliveryModel.next_retry_at)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def list_by_subscription(
        self,
        subscription_id: str,
        *,
        status: DeliveryStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[WebhookDelivery], int]:
        """List deliveries for a subscription."""
        base_stmt = select(WebhookDeliveryModel).where(
            WebhookDeliveryModel.subscription_id == subscription_id
        )
        if status:
            base_stmt = base_stmt.where(WebhookDeliveryModel.status == status)
        base_stmt = self._apply_tenant_filter(base_stmt)

        # Count query
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Data query
        stmt = base_stmt.offset(offset).limit(limit).order_by(
            WebhookDeliveryModel.created_at.desc()
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(m) for m in models], total

    async def list_by_event(
        self,
        event_id: str,
    ) -> Sequence[WebhookDelivery]:
        """List deliveries for an event."""
        stmt = select(WebhookDeliveryModel).where(
            WebhookDeliveryModel.event_id == event_id
        )
        stmt = self._apply_tenant_filter(stmt)
        stmt = stmt.order_by(WebhookDeliveryModel.created_at.desc())
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def delete_before(
        self,
        before: datetime,
        *,
        tenant_id: str | None = None,
    ) -> int:
        """Delete deliveries created before a given date."""
        stmt = delete(WebhookDeliveryModel).where(
            WebhookDeliveryModel.created_at < before
        )
        if tenant_id:
            stmt = stmt.where(WebhookDeliveryModel.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount


class SqlAlchemyWebhookRepository:
    """Unified repository for webhook operations.
    
    This class combines subscription, event, and delivery repositories
    for convenience in tasks and use cases.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._subscriptions = SqlAlchemyWebhookSubscriptionRepository(session)
        self._events = SqlAlchemyWebhookEventRepository(session)
        self._deliveries = SqlAlchemyWebhookDeliveryRepository(session)

    # Subscription operations
    async def get_subscription_by_id(
        self, subscription_id: str
    ) -> WebhookSubscription | None:
        """Get subscription by ID."""
        return await self._subscriptions.get_by_id(subscription_id)

    async def get_active_subscriptions_for_event(
        self,
        event_type: WebhookEventType,
        *,
        tenant_id: str | None = None,
    ) -> Sequence[WebhookSubscription]:
        """Get active subscriptions for an event type."""
        return await self._subscriptions.list_by_event(event_type)

    async def update_subscription(
        self, subscription: WebhookSubscription
    ) -> bool:
        """Update subscription (uses current version for optimistic locking)."""
        return await self._subscriptions.update(
            subscription, expected_version=subscription.version - 1
        )

    # Event operations
    async def save_event(
        self,
        event: WebhookEvent,
        *,
        tenant_id: str | None = None,
    ) -> None:
        """Save a webhook event."""
        await self._events.add(event)

    # Delivery operations
    async def save_delivery(
        self,
        delivery: WebhookDelivery,
        *,
        tenant_id: str | None = None,
    ) -> None:
        """Save a webhook delivery."""
        await self._deliveries.add(delivery)

    async def update_delivery(self, delivery: WebhookDelivery) -> None:
        """Update a webhook delivery."""
        await self._deliveries.update(delivery)

    async def get_pending_retries(
        self,
        before: datetime,
        *,
        limit: int = 100,
        tenant_id: str | None = None,
    ) -> Sequence[WebhookDelivery]:
        """Get deliveries pending retry."""
        return await self._deliveries.list_pending_retries(limit=limit)

    async def delete_deliveries_before(
        self,
        before: datetime,
        *,
        tenant_id: str | None = None,
    ) -> int:
        """Delete old delivery records."""
        return await self._deliveries.delete_before(before, tenant_id=tenant_id)
