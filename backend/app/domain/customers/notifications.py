"""Customer notification domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from app.domain.common.errors import ValidationError
from app.domain.common.identifiers import new_ulid


class NotificationChannel(str, Enum):
    """Channels for customer notifications."""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationType(str, Enum):
    """Types of customer notifications."""

    # Transactional
    ORDER_CONFIRMATION = "order_confirmation"
    ORDER_RECEIPT = "order_receipt"
    REFUND_PROCESSED = "refund_processed"
    PAYMENT_RECEIVED = "payment_received"

    # Loyalty
    POINTS_EARNED = "points_earned"
    POINTS_EXPIRING = "points_expiring"
    TIER_UPGRADE = "tier_upgrade"
    TIER_DOWNGRADE_WARNING = "tier_downgrade_warning"
    REWARD_AVAILABLE = "reward_available"

    # Marketing
    PROMOTIONAL = "promotional"
    NEW_PRODUCT = "new_product"
    FLASH_SALE = "flash_sale"
    BIRTHDAY_REWARD = "birthday_reward"
    ANNIVERSARY_REWARD = "anniversary_reward"

    # Engagement
    WELCOME = "welcome"
    WIN_BACK = "win_back"
    FEEDBACK_REQUEST = "feedback_request"
    SURVEY = "survey"

    # Gift Card
    GIFT_CARD_RECEIVED = "gift_card_received"
    GIFT_CARD_LOW_BALANCE = "gift_card_low_balance"
    GIFT_CARD_EXPIRING = "gift_card_expiring"


class NotificationStatus(str, Enum):
    """Status of a notification."""

    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    FAILED = "failed"
    UNSUBSCRIBED = "unsubscribed"


class NotificationPriority(str, Enum):
    """Priority levels for notifications."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass(slots=True)
class NotificationTemplate:
    """Template for customer notifications."""

    id: str
    name: str
    notification_type: NotificationType
    channel: NotificationChannel
    subject: str | None  # For email
    body_template: str
    variables: list[str]  # List of variable names expected in template
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0

    @staticmethod
    def create(
        *,
        name: str,
        notification_type: NotificationType,
        channel: NotificationChannel,
        subject: str | None = None,
        body_template: str,
        variables: list[str] | None = None,
    ) -> NotificationTemplate:
        """Create a new notification template."""
        if not name or not name.strip():
            raise ValidationError(
                "Template name is required", code="notification.invalid_name"
            )
        if not body_template or not body_template.strip():
            raise ValidationError(
                "Body template is required", code="notification.invalid_body"
            )
        if channel == NotificationChannel.EMAIL and not subject:
            raise ValidationError(
                "Subject required for email notifications",
                code="notification.subject_required",
            )

        return NotificationTemplate(
            id=new_ulid(),
            name=name.strip(),
            notification_type=notification_type,
            channel=channel,
            subject=subject.strip() if subject else None,
            body_template=body_template.strip(),
            variables=variables or [],
        )

    def render(self, context: dict[str, str]) -> tuple[str | None, str]:
        """Render the template with given context.

        Returns:
            Tuple of (rendered_subject, rendered_body)
        """
        rendered_body = self.body_template
        rendered_subject = self.subject

        for var_name in self.variables:
            placeholder = f"{{{{{var_name}}}}}"
            value = context.get(var_name, "")
            rendered_body = rendered_body.replace(placeholder, str(value))
            if rendered_subject:
                rendered_subject = rendered_subject.replace(placeholder, str(value))

        return rendered_subject, rendered_body

    def _touch(self) -> None:
        """Update timestamp and version."""
        self.updated_at = datetime.now(UTC)
        self.version += 1


@dataclass(slots=True)
class CustomerNotification:
    """A notification to be sent to a customer."""

    id: str
    customer_id: str
    notification_type: NotificationType
    channel: NotificationChannel
    priority: NotificationPriority
    subject: str | None
    body: str
    status: NotificationStatus = NotificationStatus.PENDING
    reference_id: str | None = None  # Sale ID, promotion ID, etc.
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)
    scheduled_at: datetime | None = None  # For scheduled notifications
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    opened_at: datetime | None = None
    clicked_at: datetime | None = None
    failed_reason: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0

    MAX_RETRIES = 3

    @staticmethod
    def create(
        *,
        customer_id: str,
        notification_type: NotificationType,
        channel: NotificationChannel,
        subject: str | None = None,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        reference_id: str | None = None,
        metadata: dict[str, str | int | float | bool] | None = None,
        scheduled_at: datetime | None = None,
    ) -> CustomerNotification:
        """Create a new customer notification."""
        if not customer_id:
            raise ValidationError(
                "customer_id is required", code="notification.invalid_customer_id"
            )
        if not body or not body.strip():
            raise ValidationError(
                "Notification body is required", code="notification.invalid_body"
            )
        if channel == NotificationChannel.EMAIL and not subject:
            raise ValidationError(
                "Subject required for email notifications",
                code="notification.subject_required",
            )

        return CustomerNotification(
            id=new_ulid(),
            customer_id=customer_id,
            notification_type=notification_type,
            channel=channel,
            priority=priority,
            subject=subject.strip() if subject else None,
            body=body.strip(),
            reference_id=reference_id,
            metadata=metadata or {},
            scheduled_at=scheduled_at,
        )

    @classmethod
    def from_template(
        cls,
        *,
        customer_id: str,
        template: NotificationTemplate,
        context: dict[str, str],
        priority: NotificationPriority = NotificationPriority.NORMAL,
        reference_id: str | None = None,
        metadata: dict[str, str | int | float | bool] | None = None,
        scheduled_at: datetime | None = None,
    ) -> CustomerNotification:
        """Create notification from a template."""
        subject, body = template.render(context)
        return cls.create(
            customer_id=customer_id,
            notification_type=template.notification_type,
            channel=template.channel,
            subject=subject,
            body=body,
            priority=priority,
            reference_id=reference_id,
            metadata=metadata,
            scheduled_at=scheduled_at,
        )

    def queue(self) -> None:
        """Mark notification as queued for sending."""
        if self.status not in (NotificationStatus.PENDING, NotificationStatus.FAILED):
            raise ValidationError(
                f"Cannot queue notification with status {self.status}",
                code="notification.invalid_status",
            )
        self.status = NotificationStatus.QUEUED
        self._touch()

    def mark_sent(self) -> None:
        """Mark notification as sent."""
        if self.status != NotificationStatus.QUEUED:
            raise ValidationError(
                f"Cannot mark as sent notification with status {self.status}",
                code="notification.invalid_status",
            )
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.now(UTC)
        self._touch()

    def mark_delivered(self) -> None:
        """Mark notification as delivered."""
        if self.status not in (NotificationStatus.SENT, NotificationStatus.DELIVERED):
            raise ValidationError(
                f"Cannot mark as delivered notification with status {self.status}",
                code="notification.invalid_status",
            )
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = datetime.now(UTC)
        self._touch()

    def mark_opened(self) -> None:
        """Mark notification as opened."""
        if self.status not in (
            NotificationStatus.DELIVERED,
            NotificationStatus.OPENED,
            NotificationStatus.SENT,
        ):
            raise ValidationError(
                f"Cannot mark as opened notification with status {self.status}",
                code="notification.invalid_status",
            )
        self.status = NotificationStatus.OPENED
        self.opened_at = datetime.now(UTC)
        self._touch()

    def mark_clicked(self) -> None:
        """Mark notification as clicked."""
        if self.status not in (
            NotificationStatus.OPENED,
            NotificationStatus.CLICKED,
            NotificationStatus.DELIVERED,
        ):
            raise ValidationError(
                f"Cannot mark as clicked notification with status {self.status}",
                code="notification.invalid_status",
            )
        self.status = NotificationStatus.CLICKED
        self.clicked_at = datetime.now(UTC)
        self._touch()

    def mark_failed(self, reason: str) -> None:
        """Mark notification as failed."""
        self.status = NotificationStatus.FAILED
        self.failed_reason = reason
        self.retry_count += 1
        self._touch()

    def mark_bounced(self, reason: str | None = None) -> None:
        """Mark notification as bounced."""
        self.status = NotificationStatus.BOUNCED
        self.failed_reason = reason or "Delivery bounced"
        self._touch()

    def can_retry(self) -> bool:
        """Check if notification can be retried."""
        return (
            self.status == NotificationStatus.FAILED
            and self.retry_count < self.max_retries
        )

    def is_ready_to_send(self) -> bool:
        """Check if notification is ready to be sent."""
        if self.status != NotificationStatus.PENDING:
            return False
        if self.scheduled_at and self.scheduled_at > datetime.now(UTC):
            return False
        return True

    def _touch(self) -> None:
        """Update timestamp and version."""
        self.updated_at = datetime.now(UTC)
        self.version += 1


@dataclass(slots=True)
class CustomerNotificationPreferences:
    """Customer's notification preferences."""

    id: str
    customer_id: str
    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = False
    in_app_enabled: bool = True

    # Category preferences
    transactional_enabled: bool = True  # Always recommended
    loyalty_enabled: bool = True
    marketing_enabled: bool = True  # Opt-in for marketing
    engagement_enabled: bool = True

    # Quiet hours
    quiet_hours_start: int | None = None  # Hour of day (0-23)
    quiet_hours_end: int | None = None
    timezone: str = "UTC"

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0

    @staticmethod
    def create(*, customer_id: str) -> CustomerNotificationPreferences:
        """Create default notification preferences for a customer."""
        if not customer_id:
            raise ValidationError(
                "customer_id is required", code="notification.invalid_customer_id"
            )
        return CustomerNotificationPreferences(
            id=new_ulid(),
            customer_id=customer_id,
        )

    def is_channel_enabled(self, channel: NotificationChannel) -> bool:
        """Check if a notification channel is enabled."""
        channel_map = {
            NotificationChannel.EMAIL: self.email_enabled,
            NotificationChannel.SMS: self.sms_enabled,
            NotificationChannel.PUSH: self.push_enabled,
            NotificationChannel.IN_APP: self.in_app_enabled,
        }
        return channel_map.get(channel, False)

    def is_type_enabled(self, notification_type: NotificationType) -> bool:
        """Check if a notification type is enabled based on category."""
        transactional_types = {
            NotificationType.ORDER_CONFIRMATION,
            NotificationType.ORDER_RECEIPT,
            NotificationType.REFUND_PROCESSED,
            NotificationType.PAYMENT_RECEIVED,
        }
        loyalty_types = {
            NotificationType.POINTS_EARNED,
            NotificationType.POINTS_EXPIRING,
            NotificationType.TIER_UPGRADE,
            NotificationType.TIER_DOWNGRADE_WARNING,
            NotificationType.REWARD_AVAILABLE,
        }
        marketing_types = {
            NotificationType.PROMOTIONAL,
            NotificationType.NEW_PRODUCT,
            NotificationType.FLASH_SALE,
            NotificationType.BIRTHDAY_REWARD,
            NotificationType.ANNIVERSARY_REWARD,
        }
        engagement_types = {
            NotificationType.WELCOME,
            NotificationType.WIN_BACK,
            NotificationType.FEEDBACK_REQUEST,
            NotificationType.SURVEY,
        }

        if notification_type in transactional_types:
            return self.transactional_enabled
        if notification_type in loyalty_types:
            return self.loyalty_enabled
        if notification_type in marketing_types:
            return self.marketing_enabled
        if notification_type in engagement_types:
            return self.engagement_enabled
        return True  # Default allow

    def can_receive(
        self,
        channel: NotificationChannel,
        notification_type: NotificationType,
    ) -> bool:
        """Check if customer can receive this notification."""
        return self.is_channel_enabled(channel) and self.is_type_enabled(
            notification_type
        )

    def update_channel_preferences(
        self,
        *,
        email: bool | None = None,
        sms: bool | None = None,
        push: bool | None = None,
        in_app: bool | None = None,
    ) -> None:
        """Update channel preferences."""
        if email is not None:
            self.email_enabled = email
        if sms is not None:
            self.sms_enabled = sms
        if push is not None:
            self.push_enabled = push
        if in_app is not None:
            self.in_app_enabled = in_app
        self._touch()

    def update_category_preferences(
        self,
        *,
        transactional: bool | None = None,
        loyalty: bool | None = None,
        marketing: bool | None = None,
        engagement: bool | None = None,
    ) -> None:
        """Update category preferences."""
        if transactional is not None:
            self.transactional_enabled = transactional
        if loyalty is not None:
            self.loyalty_enabled = loyalty
        if marketing is not None:
            self.marketing_enabled = marketing
        if engagement is not None:
            self.engagement_enabled = engagement
        self._touch()

    def set_quiet_hours(
        self,
        *,
        start_hour: int | None,
        end_hour: int | None,
        timezone: str = "UTC",
    ) -> None:
        """Set quiet hours for notifications."""
        if start_hour is not None and (start_hour < 0 or start_hour > 23):
            raise ValidationError(
                "Start hour must be 0-23", code="notification.invalid_hour"
            )
        if end_hour is not None and (end_hour < 0 or end_hour > 23):
            raise ValidationError(
                "End hour must be 0-23", code="notification.invalid_hour"
            )
        self.quiet_hours_start = start_hour
        self.quiet_hours_end = end_hour
        self.timezone = timezone
        self._touch()

    def _touch(self) -> None:
        """Update timestamp and version."""
        self.updated_at = datetime.now(UTC)
        self.version += 1
