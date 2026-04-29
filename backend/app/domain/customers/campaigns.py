"""Marketing campaign domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from app.domain.common.errors import ValidationError
from app.domain.common.identifiers import new_ulid
from app.domain.customers.engagement import CustomerSegment


class CampaignType(str, Enum):
    """Types of marketing campaigns."""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    COMBINED = "combined"  # Multiple channels


class CampaignStatus(str, Enum):
    """Campaign lifecycle status."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CampaignTrigger(str, Enum):
    """Trigger types for campaigns."""

    MANUAL = "manual"  # Manually triggered
    SCHEDULED = "scheduled"  # Time-based
    BIRTHDAY = "birthday"  # Customer birthday
    ANNIVERSARY = "anniversary"  # Customer signup anniversary
    WIN_BACK = "win_back"  # Inactive customer reactivation
    POST_PURCHASE = "post_purchase"  # After purchase
    CART_ABANDONED = "cart_abandoned"  # Abandoned cart (if applicable)
    LOYALTY_TIER_CHANGE = "loyalty_tier_change"  # Tier upgrade/downgrade


class TargetingCriteria(str, Enum):
    """Criteria for targeting customers."""

    ALL_CUSTOMERS = "all_customers"
    SEGMENT = "segment"
    LOYALTY_TIER = "loyalty_tier"
    PURCHASE_HISTORY = "purchase_history"
    CUSTOM_LIST = "custom_list"


@dataclass(slots=True)
class CampaignTargeting:
    """Targeting configuration for a campaign."""

    criteria: TargetingCriteria
    segments: list[CustomerSegment] = field(default_factory=list)
    loyalty_tiers: list[str] = field(default_factory=list)
    min_purchase_count: int | None = None
    min_total_spent: float | None = None
    max_total_spent: float | None = None
    custom_customer_ids: list[str] = field(default_factory=list)
    exclude_customer_ids: list[str] = field(default_factory=list)

    def validate(self) -> None:
        """Validate targeting configuration."""
        if self.criteria == TargetingCriteria.SEGMENT and not self.segments:
            raise ValidationError(
                "Segments required for segment targeting",
                code="campaign.missing_segments",
            )
        if self.criteria == TargetingCriteria.LOYALTY_TIER and not self.loyalty_tiers:
            raise ValidationError(
                "Loyalty tiers required for tier targeting",
                code="campaign.missing_tiers",
            )
        if self.criteria == TargetingCriteria.CUSTOM_LIST and not self.custom_customer_ids:
            raise ValidationError(
                "Customer IDs required for custom list targeting",
                code="campaign.missing_customers",
            )


@dataclass(slots=True)
class CampaignContent:
    """Content configuration for a campaign."""

    subject: str | None = None  # For email
    body: str = ""
    html_body: str | None = None  # For email
    call_to_action: str | None = None
    discount_code: str | None = None
    template_id: str | None = None  # Reference to NotificationTemplate

    def validate(self, campaign_type: CampaignType) -> None:
        """Validate content for campaign type."""
        if not self.body and not self.template_id:
            raise ValidationError(
                "Either body or template_id is required",
                code="campaign.missing_content",
            )
        if campaign_type == CampaignType.EMAIL and not self.subject and not self.template_id:
            raise ValidationError(
                "Subject required for email campaigns",
                code="campaign.missing_subject",
            )


@dataclass(slots=True)
class CampaignMetrics:
    """Metrics for campaign performance."""

    total_targeted: int = 0
    total_sent: int = 0
    total_delivered: int = 0
    total_opened: int = 0
    total_clicked: int = 0
    total_converted: int = 0  # Made a purchase
    total_unsubscribed: int = 0
    total_bounced: int = 0
    total_failed: int = 0
    revenue_generated: float = 0.0

    @property
    def delivery_rate(self) -> float:
        """Percentage of sent that were delivered."""
        return self.total_delivered / self.total_sent if self.total_sent > 0 else 0.0

    @property
    def open_rate(self) -> float:
        """Percentage of delivered that were opened."""
        return self.total_opened / self.total_delivered if self.total_delivered > 0 else 0.0

    @property
    def click_rate(self) -> float:
        """Percentage of opened that were clicked."""
        return self.total_clicked / self.total_opened if self.total_opened > 0 else 0.0

    @property
    def conversion_rate(self) -> float:
        """Percentage of clicked that converted."""
        return self.total_converted / self.total_clicked if self.total_clicked > 0 else 0.0

    def record_sent(self, count: int = 1) -> None:
        """Record messages sent."""
        self.total_sent += count

    def record_delivered(self, count: int = 1) -> None:
        """Record messages delivered."""
        self.total_delivered += count

    def record_opened(self, count: int = 1) -> None:
        """Record messages opened."""
        self.total_opened += count

    def record_clicked(self, count: int = 1) -> None:
        """Record messages clicked."""
        self.total_clicked += count

    def record_conversion(self, revenue: float = 0.0) -> None:
        """Record a conversion."""
        self.total_converted += 1
        self.revenue_generated += revenue


@dataclass(slots=True)
class MarketingCampaign:
    """Marketing campaign entity."""

    id: str
    name: str
    description: str
    campaign_type: CampaignType
    trigger: CampaignTrigger
    status: CampaignStatus
    targeting: CampaignTargeting
    content: CampaignContent
    metrics: CampaignMetrics

    # Scheduling
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Configuration
    send_rate_limit: int = 100  # Messages per minute
    is_recurring: bool = False
    recurrence_pattern: str | None = None  # cron expression for recurring

    # Metadata
    created_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0

    @staticmethod
    def create(
        *,
        name: str,
        description: str = "",
        campaign_type: CampaignType,
        trigger: CampaignTrigger = CampaignTrigger.MANUAL,
        targeting: CampaignTargeting | None = None,
        content: CampaignContent | None = None,
        created_by: str | None = None,
    ) -> MarketingCampaign:
        """Create a new marketing campaign."""
        if not name or not name.strip():
            raise ValidationError(
                "Campaign name is required",
                code="campaign.invalid_name",
            )

        campaign = MarketingCampaign(
            id=new_ulid(),
            name=name.strip(),
            description=description.strip() if description else "",
            campaign_type=campaign_type,
            trigger=trigger,
            status=CampaignStatus.DRAFT,
            targeting=targeting or CampaignTargeting(criteria=TargetingCriteria.ALL_CUSTOMERS),
            content=content or CampaignContent(),
            metrics=CampaignMetrics(),
            created_by=created_by,
        )
        return campaign

    def schedule(self, scheduled_at: datetime) -> None:
        """Schedule the campaign for a specific time."""
        if self.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
            raise ValidationError(
                f"Cannot schedule campaign with status {self.status}",
                code="campaign.invalid_status",
            )
        if scheduled_at <= datetime.now(UTC):
            raise ValidationError(
                "Scheduled time must be in the future",
                code="campaign.invalid_schedule",
            )

        # Validate targeting and content
        self.targeting.validate()
        self.content.validate(self.campaign_type)

        self.scheduled_at = scheduled_at
        self.status = CampaignStatus.SCHEDULED
        self._touch()

    def start(self) -> None:
        """Start executing the campaign."""
        if self.status not in (CampaignStatus.DRAFT, CampaignStatus.SCHEDULED, CampaignStatus.PAUSED):
            raise ValidationError(
                f"Cannot start campaign with status {self.status}",
                code="campaign.invalid_status",
            )

        # Validate before starting
        self.targeting.validate()
        self.content.validate(self.campaign_type)

        self.status = CampaignStatus.RUNNING
        self.started_at = datetime.now(UTC)
        self._touch()

    def pause(self) -> None:
        """Pause a running campaign."""
        if self.status != CampaignStatus.RUNNING:
            raise ValidationError(
                f"Cannot pause campaign with status {self.status}",
                code="campaign.invalid_status",
            )
        self.status = CampaignStatus.PAUSED
        self._touch()

    def resume(self) -> None:
        """Resume a paused campaign."""
        if self.status != CampaignStatus.PAUSED:
            raise ValidationError(
                f"Cannot resume campaign with status {self.status}",
                code="campaign.invalid_status",
            )
        self.status = CampaignStatus.RUNNING
        self._touch()

    def complete(self) -> None:
        """Mark campaign as completed."""
        if self.status != CampaignStatus.RUNNING:
            raise ValidationError(
                f"Cannot complete campaign with status {self.status}",
                code="campaign.invalid_status",
            )
        self.status = CampaignStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
        self._touch()

    def cancel(self) -> None:
        """Cancel the campaign."""
        if self.status in (CampaignStatus.COMPLETED, CampaignStatus.CANCELLED):
            raise ValidationError(
                f"Cannot cancel campaign with status {self.status}",
                code="campaign.invalid_status",
            )
        self.status = CampaignStatus.CANCELLED
        self._touch()

    def update_content(self, content: CampaignContent) -> None:
        """Update campaign content."""
        if self.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
            raise ValidationError(
                "Cannot update content of active campaign",
                code="campaign.invalid_status",
            )
        content.validate(self.campaign_type)
        self.content = content
        self._touch()

    def update_targeting(self, targeting: CampaignTargeting) -> None:
        """Update campaign targeting."""
        if self.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
            raise ValidationError(
                "Cannot update targeting of active campaign",
                code="campaign.invalid_status",
            )
        targeting.validate()
        self.targeting = targeting
        self._touch()

    def set_targeted_count(self, count: int) -> None:
        """Set the total number of targeted customers."""
        self.metrics.total_targeted = count
        self._touch()

    def is_ready_to_run(self) -> bool:
        """Check if campaign is ready to run."""
        if self.status != CampaignStatus.SCHEDULED:
            return False
        if not self.scheduled_at:
            return False
        return self.scheduled_at <= datetime.now(UTC)

    def _touch(self) -> None:
        """Update timestamp and version."""
        self.updated_at = datetime.now(UTC)
        self.version += 1


@dataclass(slots=True)
class CampaignRecipient:
    """Tracking for individual campaign recipients."""

    id: str
    campaign_id: str
    customer_id: str
    notification_id: str | None = None  # Link to CustomerNotification
    status: str = "pending"  # pending, sent, delivered, opened, clicked, converted
    sent_at: datetime | None = None
    opened_at: datetime | None = None
    clicked_at: datetime | None = None
    converted_at: datetime | None = None
    conversion_value: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def create(
        *,
        campaign_id: str,
        customer_id: str,
    ) -> CampaignRecipient:
        """Create a new campaign recipient record."""
        return CampaignRecipient(
            id=new_ulid(),
            campaign_id=campaign_id,
            customer_id=customer_id,
        )

    def mark_sent(self, notification_id: str) -> None:
        """Mark as sent."""
        self.notification_id = notification_id
        self.status = "sent"
        self.sent_at = datetime.now(UTC)

    def mark_opened(self) -> None:
        """Mark as opened."""
        self.status = "opened"
        self.opened_at = datetime.now(UTC)

    def mark_clicked(self) -> None:
        """Mark as clicked."""
        self.status = "clicked"
        self.clicked_at = datetime.now(UTC)

    def mark_converted(self, value: float = 0.0) -> None:
        """Mark as converted with optional value."""
        self.status = "converted"
        self.converted_at = datetime.now(UTC)
        self.conversion_value = value


@dataclass(slots=True)
class CustomerFeedback:
    """Customer feedback entity."""

    id: str
    customer_id: str
    feedback_type: str  # review, survey, complaint, suggestion
    subject: str
    content: str
    rating: int | None = None  # 1-5 stars
    reference_id: str | None = None  # Sale ID, product ID, etc.
    reference_type: str | None = None  # sale, product, service
    status: str = "pending"  # pending, reviewed, resolved, archived
    response: str | None = None
    responded_at: datetime | None = None
    responded_by: str | None = None
    is_public: bool = False  # Can be shown as testimonial
    sentiment_score: float | None = None  # -1 to 1 sentiment analysis
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0

    @staticmethod
    def create(
        *,
        customer_id: str,
        feedback_type: str,
        subject: str,
        content: str,
        rating: int | None = None,
        reference_id: str | None = None,
        reference_type: str | None = None,
    ) -> CustomerFeedback:
        """Create customer feedback."""
        if not customer_id:
            raise ValidationError(
                "customer_id is required",
                code="feedback.invalid_customer",
            )
        if not subject or not subject.strip():
            raise ValidationError(
                "Subject is required",
                code="feedback.invalid_subject",
            )
        if not content or not content.strip():
            raise ValidationError(
                "Content is required",
                code="feedback.invalid_content",
            )
        if rating is not None and (rating < 1 or rating > 5):
            raise ValidationError(
                "Rating must be 1-5",
                code="feedback.invalid_rating",
            )

        return CustomerFeedback(
            id=new_ulid(),
            customer_id=customer_id,
            feedback_type=feedback_type,
            subject=subject.strip(),
            content=content.strip(),
            rating=rating,
            reference_id=reference_id,
            reference_type=reference_type,
        )

    def respond(self, response: str, responded_by: str) -> None:
        """Add a response to feedback."""
        if not response or not response.strip():
            raise ValidationError(
                "Response is required",
                code="feedback.invalid_response",
            )
        self.response = response.strip()
        self.responded_by = responded_by
        self.responded_at = datetime.now(UTC)
        self.status = "reviewed"
        self._touch()

    def resolve(self) -> None:
        """Mark feedback as resolved."""
        self.status = "resolved"
        self._touch()

    def archive(self) -> None:
        """Archive the feedback."""
        self.status = "archived"
        self._touch()

    def set_public(self, is_public: bool) -> None:
        """Set whether feedback can be shown publicly."""
        self.is_public = is_public
        self._touch()

    def set_sentiment(self, score: float) -> None:
        """Set sentiment analysis score."""
        if score < -1 or score > 1:
            raise ValidationError(
                "Sentiment score must be between -1 and 1",
                code="feedback.invalid_sentiment",
            )
        self.sentiment_score = score
        self._touch()

    def _touch(self) -> None:
        """Update timestamp and version."""
        self.updated_at = datetime.now(UTC)
        self.version += 1
