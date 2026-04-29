"""Customer engagement tracking domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from app.domain.common.errors import ValidationError
from app.domain.common.identifiers import new_ulid


class EngagementEventType(str, Enum):
    """Types of customer engagement events."""

    # Purchase events
    PURCHASE = "purchase"
    REPEAT_PURCHASE = "repeat_purchase"
    HIGH_VALUE_PURCHASE = "high_value_purchase"

    # Account events
    ACCOUNT_CREATED = "account_created"
    PROFILE_UPDATED = "profile_updated"
    LOYALTY_ENROLLED = "loyalty_enrolled"
    TIER_UPGRADED = "tier_upgraded"

    # Interaction events
    VISITED_STORE = "visited_store"
    APP_LOGIN = "app_login"
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    SURVEY_COMPLETED = "survey_completed"

    # Reward events
    POINTS_EARNED = "points_earned"
    POINTS_REDEEMED = "points_redeemed"
    COUPON_USED = "coupon_used"
    GIFT_CARD_PURCHASED = "gift_card_purchased"
    GIFT_CARD_REDEEMED = "gift_card_redeemed"

    # Feedback events
    REVIEW_SUBMITTED = "review_submitted"
    FEEDBACK_GIVEN = "feedback_given"
    COMPLAINT_FILED = "complaint_filed"

    # Churn risk events
    INACTIVE_WARNING = "inactive_warning"
    WIN_BACK_ATTEMPT = "win_back_attempt"


class CustomerSegment(str, Enum):
    """Customer segments for marketing and engagement."""

    NEW = "new"  # First 30 days
    ACTIVE = "active"  # Purchased in last 30 days
    ENGAGED = "engaged"  # High interaction frequency
    LOYAL = "loyal"  # Silver+ tier or 3+ purchases
    VIP = "vip"  # Gold+ tier or high spend
    AT_RISK = "at_risk"  # No purchase in 60-90 days
    CHURNED = "churned"  # No purchase in 90+ days
    WIN_BACK = "win_back"  # Churned but showing interest


@dataclass(slots=True)
class EngagementEvent:
    """Record of a customer engagement event."""

    id: str
    customer_id: str
    event_type: EngagementEventType
    reference_id: str | None  # Sale ID, campaign ID, etc.
    metadata: dict[str, str | int | float | bool]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def create(
        *,
        customer_id: str,
        event_type: EngagementEventType,
        reference_id: str | None = None,
        metadata: dict[str, str | int | float | bool] | None = None,
    ) -> EngagementEvent:
        """Create a new engagement event."""
        if not customer_id:
            raise ValidationError(
                "customer_id is required", code="engagement.invalid_customer_id"
            )
        return EngagementEvent(
            id=new_ulid(),
            customer_id=customer_id,
            event_type=event_type,
            reference_id=reference_id,
            metadata=metadata or {},
        )


@dataclass(slots=True)
class CustomerEngagementProfile:
    """Aggregated engagement metrics for a customer."""

    id: str
    customer_id: str
    segment: CustomerSegment = CustomerSegment.NEW

    # Purchase metrics
    total_purchases: int = 0
    total_spent: Decimal = field(default_factory=lambda: Decimal("0"))
    average_order_value: Decimal = field(default_factory=lambda: Decimal("0"))
    last_purchase_at: datetime | None = None

    # Engagement metrics
    total_interactions: int = 0
    last_interaction_at: datetime | None = None
    email_open_rate: float = 0.0
    email_click_rate: float = 0.0

    # Loyalty metrics
    loyalty_tier: str | None = None
    current_points: int = 0
    lifetime_points: int = 0

    # Dates
    first_seen_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0

    @staticmethod
    def create(*, customer_id: str) -> CustomerEngagementProfile:
        """Create a new engagement profile for a customer."""
        if not customer_id:
            raise ValidationError(
                "customer_id is required", code="engagement.invalid_customer_id"
            )
        return CustomerEngagementProfile(
            id=new_ulid(),
            customer_id=customer_id,
        )

    def record_purchase(
        self,
        *,
        amount: Decimal,
        purchase_date: datetime | None = None,
    ) -> None:
        """Record a purchase and update metrics."""
        if amount <= 0:
            raise ValidationError(
                "Purchase amount must be positive",
                code="engagement.invalid_amount",
            )

        self.total_purchases += 1
        self.total_spent += amount
        self.average_order_value = self.total_spent / self.total_purchases
        self.last_purchase_at = purchase_date or datetime.now(UTC)
        self.total_interactions += 1
        self.last_interaction_at = self.last_purchase_at
        self._update_segment()
        self._touch()

    def record_interaction(self, *, event_type: EngagementEventType) -> None:
        """Record a customer interaction."""
        self.total_interactions += 1
        self.last_interaction_at = datetime.now(UTC)
        self._update_segment()
        self._touch()

    def update_email_metrics(
        self,
        *,
        emails_sent: int,
        emails_opened: int,
        emails_clicked: int,
    ) -> None:
        """Update email engagement metrics."""
        if emails_sent > 0:
            self.email_open_rate = emails_opened / emails_sent
            self.email_click_rate = emails_clicked / emails_sent
        self._touch()

    def sync_loyalty(
        self,
        *,
        tier: str,
        current_points: int,
        lifetime_points: int,
    ) -> None:
        """Sync loyalty program data."""
        self.loyalty_tier = tier
        self.current_points = current_points
        self.lifetime_points = lifetime_points
        self._update_segment()
        self._touch()

    def _update_segment(self) -> None:
        """Update customer segment based on metrics."""
        now = datetime.now(UTC)

        # Calculate days since last purchase
        days_since_purchase = None
        if self.last_purchase_at:
            days_since_purchase = (now - self.last_purchase_at).days

        # Calculate days since first seen
        days_since_first_seen = (now - self.first_seen_at).days

        # Determine segment
        if days_since_purchase is None:
            # Never purchased
            if days_since_first_seen <= 30:
                self.segment = CustomerSegment.NEW
            else:
                self.segment = CustomerSegment.AT_RISK
        elif days_since_purchase > 90:
            self.segment = CustomerSegment.CHURNED
        elif days_since_purchase > 60:
            self.segment = CustomerSegment.AT_RISK
        elif self.loyalty_tier in ("gold", "platinum"):
            self.segment = CustomerSegment.VIP
        elif self.loyalty_tier in ("silver",) or self.total_purchases >= 3:
            self.segment = CustomerSegment.LOYAL
        elif self.total_interactions >= 10:
            self.segment = CustomerSegment.ENGAGED
        elif days_since_purchase <= 30:
            self.segment = CustomerSegment.ACTIVE
        elif days_since_first_seen <= 30:
            self.segment = CustomerSegment.NEW
        else:
            self.segment = CustomerSegment.ACTIVE

    def is_high_value(self) -> bool:
        """Check if customer is high-value based on spending."""
        return self.total_spent >= Decimal("1000") or self.segment in (
            CustomerSegment.VIP,
            CustomerSegment.LOYAL,
        )

    def is_at_churn_risk(self) -> bool:
        """Check if customer is at risk of churning."""
        return self.segment in (CustomerSegment.AT_RISK, CustomerSegment.CHURNED)

    def _touch(self) -> None:
        """Update timestamp and version."""
        self.updated_at = datetime.now(UTC)
        self.version += 1
