"""Repository implementations for customer notifications."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.customers.notifications import (
    CustomerNotification,
    CustomerNotificationPreferences,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    NotificationTemplate,
    NotificationType,
)
from app.infrastructure.db.models.notification_model import (
    CustomerNotificationModel,
    CustomerNotificationPreferencesModel,
    NotificationTemplateModel,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class SqlAlchemyNotificationTemplateRepository:
    """Repository for notification templates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, template: NotificationTemplate) -> None:
        """Save a notification template."""
        model = NotificationTemplateModel(
            id=template.id,
            name=template.name,
            notification_type=template.notification_type,
            channel=template.channel,
            subject=template.subject,
            body_template=template.body_template,
            variables=template.variables,
            is_active=template.is_active,
            created_at=template.created_at,
            updated_at=template.updated_at,
            version=template.version,
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, template: NotificationTemplate) -> None:
        """Update an existing template."""
        await self._session.execute(
            update(NotificationTemplateModel)
            .where(NotificationTemplateModel.id == template.id)
            .values(
                name=template.name,
                notification_type=template.notification_type,
                channel=template.channel,
                subject=template.subject,
                body_template=template.body_template,
                variables=template.variables,
                is_active=template.is_active,
                updated_at=template.updated_at,
                version=template.version,
            )
        )

    async def get_by_id(self, template_id: str) -> NotificationTemplate | None:
        """Get template by ID."""
        result = await self._session.execute(
            select(NotificationTemplateModel).where(
                NotificationTemplateModel.id == template_id
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_name(self, name: str) -> NotificationTemplate | None:
        """Get template by name."""
        result = await self._session.execute(
            select(NotificationTemplateModel).where(
                NotificationTemplateModel.name == name
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_type_and_channel(
        self,
        notification_type: NotificationType,
        channel: NotificationChannel,
    ) -> NotificationTemplate | None:
        """Get active template by type and channel."""
        result = await self._session.execute(
            select(NotificationTemplateModel).where(
                and_(
                    NotificationTemplateModel.notification_type == notification_type,
                    NotificationTemplateModel.channel == channel,
                    NotificationTemplateModel.is_active == True,  # noqa: E712
                )
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_active(
        self,
        channel: NotificationChannel | None = None,
    ) -> Sequence[NotificationTemplate]:
        """List active templates, optionally filtered by channel."""
        query = select(NotificationTemplateModel).where(
            NotificationTemplateModel.is_active == True  # noqa: E712
        )
        if channel:
            query = query.where(NotificationTemplateModel.channel == channel)
        query = query.order_by(NotificationTemplateModel.name)

        result = await self._session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    def _to_entity(self, model: NotificationTemplateModel) -> NotificationTemplate:
        """Convert model to entity."""
        return NotificationTemplate(
            id=model.id,
            name=model.name,
            notification_type=model.notification_type,
            channel=model.channel,
            subject=model.subject,
            body_template=model.body_template,
            variables=list(model.variables) if model.variables else [],
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )


class SqlAlchemyCustomerNotificationRepository:
    """Repository for customer notifications."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, notification: CustomerNotification) -> None:
        """Save a notification."""
        model = CustomerNotificationModel(
            id=notification.id,
            customer_id=notification.customer_id,
            notification_type=notification.notification_type,
            channel=notification.channel,
            priority=notification.priority,
            subject=notification.subject,
            body=notification.body,
            status=notification.status,
            reference_id=notification.reference_id,
            metadata_json=notification.metadata,
            scheduled_at=notification.scheduled_at,
            sent_at=notification.sent_at,
            delivered_at=notification.delivered_at,
            opened_at=notification.opened_at,
            clicked_at=notification.clicked_at,
            failed_reason=notification.failed_reason,
            retry_count=notification.retry_count,
            max_retries=notification.max_retries,
            created_at=notification.created_at,
            updated_at=notification.updated_at,
            version=notification.version,
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, notification: CustomerNotification) -> None:
        """Update notification status."""
        await self._session.execute(
            update(CustomerNotificationModel)
            .where(CustomerNotificationModel.id == notification.id)
            .values(
                status=notification.status,
                sent_at=notification.sent_at,
                delivered_at=notification.delivered_at,
                opened_at=notification.opened_at,
                clicked_at=notification.clicked_at,
                failed_reason=notification.failed_reason,
                retry_count=notification.retry_count,
                updated_at=notification.updated_at,
                version=notification.version,
            )
        )

    async def get_by_id(self, notification_id: str) -> CustomerNotification | None:
        """Get notification by ID."""
        result = await self._session.execute(
            select(CustomerNotificationModel).where(
                CustomerNotificationModel.id == notification_id
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_pending_for_sending(
        self,
        limit: int = 100,
    ) -> Sequence[CustomerNotification]:
        """Get notifications ready to be sent."""
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(CustomerNotificationModel)
            .where(
                and_(
                    CustomerNotificationModel.status == NotificationStatus.PENDING,
                    (
                        (CustomerNotificationModel.scheduled_at.is_(None))
                        | (CustomerNotificationModel.scheduled_at <= now)
                    ),
                )
            )
            .order_by(
                CustomerNotificationModel.priority.desc(),
                CustomerNotificationModel.created_at,
            )
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_failed_for_retry(
        self,
        limit: int = 50,
    ) -> Sequence[CustomerNotification]:
        """Get failed notifications eligible for retry."""
        result = await self._session.execute(
            select(CustomerNotificationModel)
            .where(
                and_(
                    CustomerNotificationModel.status == NotificationStatus.FAILED,
                    CustomerNotificationModel.retry_count
                    < CustomerNotificationModel.max_retries,
                )
            )
            .order_by(CustomerNotificationModel.updated_at)
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_by_customer(
        self,
        customer_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[CustomerNotification]:
        """List notifications for a customer."""
        result = await self._session.execute(
            select(CustomerNotificationModel)
            .where(CustomerNotificationModel.customer_id == customer_id)
            .order_by(CustomerNotificationModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_status(
        self,
        status: NotificationStatus | None = None,
        since: datetime | None = None,
    ) -> dict[str, int]:
        """Count notifications by status."""
        query = select(
            CustomerNotificationModel.status,
            func.count(CustomerNotificationModel.id),
        ).group_by(CustomerNotificationModel.status)

        if since:
            query = query.where(CustomerNotificationModel.created_at >= since)

        result = await self._session.execute(query)
        return {row[0].value: row[1] for row in result.all()}

    async def get_engagement_stats(
        self,
        customer_id: str,
        days: int = 30,
    ) -> dict[str, float]:
        """Get email engagement stats for a customer."""
        since = datetime.now(UTC) - timedelta(days=days)

        # Count total email notifications
        total_result = await self._session.execute(
            select(func.count(CustomerNotificationModel.id)).where(
                and_(
                    CustomerNotificationModel.customer_id == customer_id,
                    CustomerNotificationModel.channel == NotificationChannel.EMAIL,
                    CustomerNotificationModel.created_at >= since,
                    CustomerNotificationModel.status.in_(
                        [
                            NotificationStatus.SENT,
                            NotificationStatus.DELIVERED,
                            NotificationStatus.OPENED,
                            NotificationStatus.CLICKED,
                        ]
                    ),
                )
            )
        )
        total = total_result.scalar() or 0

        if total == 0:
            return {"open_rate": 0.0, "click_rate": 0.0}

        # Count opened
        opened_result = await self._session.execute(
            select(func.count(CustomerNotificationModel.id)).where(
                and_(
                    CustomerNotificationModel.customer_id == customer_id,
                    CustomerNotificationModel.channel == NotificationChannel.EMAIL,
                    CustomerNotificationModel.created_at >= since,
                    CustomerNotificationModel.opened_at.isnot(None),
                )
            )
        )
        opened = opened_result.scalar() or 0

        # Count clicked
        clicked_result = await self._session.execute(
            select(func.count(CustomerNotificationModel.id)).where(
                and_(
                    CustomerNotificationModel.customer_id == customer_id,
                    CustomerNotificationModel.channel == NotificationChannel.EMAIL,
                    CustomerNotificationModel.created_at >= since,
                    CustomerNotificationModel.clicked_at.isnot(None),
                )
            )
        )
        clicked = clicked_result.scalar() or 0

        return {
            "open_rate": opened / total if total > 0 else 0.0,
            "click_rate": clicked / total if total > 0 else 0.0,
        }

    def _to_entity(self, model: CustomerNotificationModel) -> CustomerNotification:
        """Convert model to entity."""
        return CustomerNotification(
            id=model.id,
            customer_id=model.customer_id,
            notification_type=model.notification_type,
            channel=model.channel,
            priority=model.priority,
            subject=model.subject,
            body=model.body,
            status=model.status,
            reference_id=model.reference_id,
            metadata=dict(model.metadata_json) if model.metadata_json else {},
            scheduled_at=model.scheduled_at,
            sent_at=model.sent_at,
            delivered_at=model.delivered_at,
            opened_at=model.opened_at,
            clicked_at=model.clicked_at,
            failed_reason=model.failed_reason,
            retry_count=model.retry_count,
            max_retries=model.max_retries,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )


class SqlAlchemyNotificationPreferencesRepository:
    """Repository for customer notification preferences."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, preferences: CustomerNotificationPreferences) -> None:
        """Save notification preferences."""
        model = CustomerNotificationPreferencesModel(
            id=preferences.id,
            customer_id=preferences.customer_id,
            email_enabled=preferences.email_enabled,
            sms_enabled=preferences.sms_enabled,
            push_enabled=preferences.push_enabled,
            in_app_enabled=preferences.in_app_enabled,
            transactional_enabled=preferences.transactional_enabled,
            loyalty_enabled=preferences.loyalty_enabled,
            marketing_enabled=preferences.marketing_enabled,
            engagement_enabled=preferences.engagement_enabled,
            quiet_hours_start=preferences.quiet_hours_start,
            quiet_hours_end=preferences.quiet_hours_end,
            timezone=preferences.timezone,
            created_at=preferences.created_at,
            updated_at=preferences.updated_at,
            version=preferences.version,
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, preferences: CustomerNotificationPreferences) -> None:
        """Update preferences."""
        await self._session.execute(
            update(CustomerNotificationPreferencesModel)
            .where(CustomerNotificationPreferencesModel.id == preferences.id)
            .values(
                email_enabled=preferences.email_enabled,
                sms_enabled=preferences.sms_enabled,
                push_enabled=preferences.push_enabled,
                in_app_enabled=preferences.in_app_enabled,
                transactional_enabled=preferences.transactional_enabled,
                loyalty_enabled=preferences.loyalty_enabled,
                marketing_enabled=preferences.marketing_enabled,
                engagement_enabled=preferences.engagement_enabled,
                quiet_hours_start=preferences.quiet_hours_start,
                quiet_hours_end=preferences.quiet_hours_end,
                timezone=preferences.timezone,
                updated_at=preferences.updated_at,
                version=preferences.version,
            )
        )

    async def get_by_customer_id(
        self,
        customer_id: str,
    ) -> CustomerNotificationPreferences | None:
        """Get preferences by customer ID."""
        result = await self._session.execute(
            select(CustomerNotificationPreferencesModel).where(
                CustomerNotificationPreferencesModel.customer_id == customer_id
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_or_create(
        self,
        customer_id: str,
    ) -> CustomerNotificationPreferences:
        """Get existing preferences or create defaults."""
        existing = await self.get_by_customer_id(customer_id)
        if existing:
            return existing

        # Create default preferences
        preferences = CustomerNotificationPreferences.create(customer_id=customer_id)
        await self.save(preferences)
        return preferences

    def _to_entity(
        self,
        model: CustomerNotificationPreferencesModel,
    ) -> CustomerNotificationPreferences:
        """Convert model to entity."""
        return CustomerNotificationPreferences(
            id=model.id,
            customer_id=model.customer_id,
            email_enabled=model.email_enabled,
            sms_enabled=model.sms_enabled,
            push_enabled=model.push_enabled,
            in_app_enabled=model.in_app_enabled,
            transactional_enabled=model.transactional_enabled,
            loyalty_enabled=model.loyalty_enabled,
            marketing_enabled=model.marketing_enabled,
            engagement_enabled=model.engagement_enabled,
            quiet_hours_start=model.quiet_hours_start,
            quiet_hours_end=model.quiet_hours_end,
            timezone=model.timezone,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )
