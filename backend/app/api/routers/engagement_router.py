"""Customer engagement API router."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import MANAGEMENT_ROLES, SALES_ROLES, require_roles
from app.domain.auth.entities import User
from app.domain.common.errors import NotFoundError, ValidationError
from app.domain.customers.campaigns import (
    CampaignContent,
    CampaignRecipient,
    CampaignStatus,
    CampaignTargeting,
    CampaignTrigger,
    CampaignType,
    CustomerFeedback,
    MarketingCampaign,
    TargetingCriteria,
)
from app.domain.customers.engagement import CustomerSegment, EngagementEvent, EngagementEventType
from app.domain.customers.notifications import (
    CustomerNotification,
    CustomerNotificationPreferences,
    NotificationChannel,
    NotificationPriority,
    NotificationType,
)
from app.infrastructure.db.repositories.campaign_repository import (
    SqlAlchemyCampaignRecipientRepository,
    SqlAlchemyCampaignRepository,
    SqlAlchemyFeedbackRepository,
)
from app.infrastructure.db.repositories.customer_repository import SqlAlchemyCustomerRepository
from app.infrastructure.db.repositories.engagement_repository import (
    SqlAlchemyEngagementEventRepository,
    SqlAlchemyEngagementProfileRepository,
)
from app.infrastructure.db.repositories.notification_repository import (
    SqlAlchemyCustomerNotificationRepository,
    SqlAlchemyNotificationPreferencesRepository,
    SqlAlchemyNotificationTemplateRepository,
)
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/engagement", tags=["engagement"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class TargetingRequest(BaseModel):
    """Targeting configuration request."""

    criteria: str = "all_customers"
    segments: list[str] = Field(default_factory=list)
    loyalty_tiers: list[str] = Field(default_factory=list)
    min_purchase_count: int | None = None
    min_total_spent: float | None = None
    custom_customer_ids: list[str] = Field(default_factory=list)


class ContentRequest(BaseModel):
    """Campaign content request."""

    subject: str | None = None
    body: str
    html_body: str | None = None
    call_to_action: str | None = None
    discount_code: str | None = None
    template_id: str | None = None


class CampaignCreateRequest(BaseModel):
    """Request to create a marketing campaign."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    campaign_type: str = "email"
    trigger: str = "manual"
    targeting: TargetingRequest | None = None
    content: ContentRequest | None = None


class CampaignUpdateRequest(BaseModel):
    """Request to update a campaign."""

    name: str | None = None
    description: str | None = None
    targeting: TargetingRequest | None = None
    content: ContentRequest | None = None


class CampaignScheduleRequest(BaseModel):
    """Request to schedule a campaign."""

    scheduled_at: datetime


class CampaignMetricsOut(BaseModel):
    """Campaign metrics output."""

    total_targeted: int
    total_sent: int
    total_delivered: int
    total_opened: int
    total_clicked: int
    total_converted: int
    total_failed: int
    revenue_generated: float
    delivery_rate: float
    open_rate: float
    click_rate: float
    conversion_rate: float


class CampaignOut(BaseModel):
    """Campaign output."""

    id: str
    name: str
    description: str
    campaign_type: str
    trigger: str
    status: str
    scheduled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    is_recurring: bool
    metrics: CampaignMetricsOut
    created_at: datetime
    updated_at: datetime


class CampaignListOut(BaseModel):
    """Campaign list output."""

    campaigns: list[CampaignOut]
    total: int


class NotificationPreferencesRequest(BaseModel):
    """Request to update notification preferences."""

    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    push_enabled: bool | None = None
    marketing_enabled: bool | None = None
    loyalty_enabled: bool | None = None
    quiet_hours_start: int | None = None
    quiet_hours_end: int | None = None


class NotificationPreferencesOut(BaseModel):
    """Notification preferences output."""

    customer_id: str
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    in_app_enabled: bool
    transactional_enabled: bool
    loyalty_enabled: bool
    marketing_enabled: bool
    engagement_enabled: bool
    quiet_hours_start: int | None
    quiet_hours_end: int | None
    timezone: str


class FeedbackCreateRequest(BaseModel):
    """Request to create customer feedback."""

    customer_id: str
    feedback_type: str = "review"
    subject: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    rating: int | None = Field(None, ge=1, le=5)
    reference_id: str | None = None
    reference_type: str | None = None


class FeedbackResponseRequest(BaseModel):
    """Request to respond to feedback."""

    response: str = Field(..., min_length=1)


class FeedbackOut(BaseModel):
    """Feedback output."""

    id: str
    customer_id: str
    feedback_type: str
    subject: str
    content: str
    rating: int | None
    reference_id: str | None
    reference_type: str | None
    status: str
    response: str | None
    responded_at: datetime | None
    is_public: bool
    sentiment_score: float | None
    created_at: datetime


class FeedbackListOut(BaseModel):
    """Feedback list output."""

    feedback: list[FeedbackOut]
    total: int


class EngagementProfileOut(BaseModel):
    """Customer engagement profile output."""

    customer_id: str
    segment: str
    total_purchases: int
    total_spent: float
    average_order_value: float
    last_purchase_at: datetime | None
    total_interactions: int
    email_open_rate: float
    email_click_rate: float
    loyalty_tier: str | None
    current_points: int
    lifetime_points: int
    first_seen_at: datetime


class SegmentStatsOut(BaseModel):
    """Segment statistics output."""

    segment: str
    count: int
    avg_spent: float
    avg_purchases: float
    avg_open_rate: float


class EngagementDashboardOut(BaseModel):
    """Engagement dashboard output."""

    segment_stats: list[SegmentStatsOut]
    total_customers: int
    at_risk_count: int
    vip_count: int
    avg_rating: float
    pending_feedback: int


# ============================================================================
# Campaign Endpoints
# ============================================================================


@router.post("/campaigns", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    request: CampaignCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> CampaignOut:
    """Create a new marketing campaign."""
    try:
        targeting = None
        if request.targeting:
            targeting = CampaignTargeting(
                criteria=TargetingCriteria(request.targeting.criteria),
                segments=[CustomerSegment(s) for s in request.targeting.segments],
                loyalty_tiers=request.targeting.loyalty_tiers,
                min_purchase_count=request.targeting.min_purchase_count,
                min_total_spent=request.targeting.min_total_spent,
                custom_customer_ids=request.targeting.custom_customer_ids,
            )

        content = None
        if request.content:
            content = CampaignContent(
                subject=request.content.subject,
                body=request.content.body,
                html_body=request.content.html_body,
                call_to_action=request.content.call_to_action,
                discount_code=request.content.discount_code,
                template_id=request.content.template_id,
            )

        campaign = MarketingCampaign.create(
            name=request.name,
            description=request.description,
            campaign_type=CampaignType(request.campaign_type),
            trigger=CampaignTrigger(request.trigger),
            targeting=targeting,
            content=content,
        )

        repo = SqlAlchemyCampaignRepository(session)
        await repo.save(campaign)
        await session.commit()

        return _campaign_to_out(campaign)

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/campaigns", response_model=CampaignListOut)
async def list_campaigns(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
    status_filter: str | None = Query(None, alias="status"),
    campaign_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> CampaignListOut:
    """List marketing campaigns."""
    repo = SqlAlchemyCampaignRepository(session)

    status_enum = CampaignStatus(status_filter) if status_filter else None
    type_enum = CampaignType(campaign_type) if campaign_type else None

    campaigns = await repo.list_by_status(
        status=status_enum,
        campaign_type=type_enum,
        limit=limit,
        offset=offset,
    )

    return CampaignListOut(
        campaigns=[_campaign_to_out(c) for c in campaigns],
        total=len(campaigns),
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> CampaignOut:
    """Get a campaign by ID."""
    repo = SqlAlchemyCampaignRepository(session)
    campaign = await repo.get_by_id(campaign_id)

    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    return _campaign_to_out(campaign)


@router.put("/campaigns/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: str,
    request: CampaignUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> CampaignOut:
    """Update a campaign."""
    repo = SqlAlchemyCampaignRepository(session)
    campaign = await repo.get_by_id(campaign_id)

    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    try:
        if request.name:
            campaign.name = request.name
        if request.description is not None:
            campaign.description = request.description

        if request.targeting:
            targeting = CampaignTargeting(
                criteria=TargetingCriteria(request.targeting.criteria),
                segments=[CustomerSegment(s) for s in request.targeting.segments],
                loyalty_tiers=request.targeting.loyalty_tiers,
                min_purchase_count=request.targeting.min_purchase_count,
                min_total_spent=request.targeting.min_total_spent,
                custom_customer_ids=request.targeting.custom_customer_ids,
            )
            campaign.update_targeting(targeting)

        if request.content:
            content = CampaignContent(
                subject=request.content.subject,
                body=request.content.body,
                html_body=request.content.html_body,
                call_to_action=request.content.call_to_action,
                discount_code=request.content.discount_code,
                template_id=request.content.template_id,
            )
            campaign.update_content(content)

        await repo.update(campaign)
        await session.commit()

        return _campaign_to_out(campaign)

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/campaigns/{campaign_id}/schedule", response_model=CampaignOut)
async def schedule_campaign(
    campaign_id: str,
    request: CampaignScheduleRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> CampaignOut:
    """Schedule a campaign."""
    repo = SqlAlchemyCampaignRepository(session)
    campaign = await repo.get_by_id(campaign_id)

    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    try:
        campaign.schedule(request.scheduled_at)
        await repo.update(campaign)
        await session.commit()

        return _campaign_to_out(campaign)

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/campaigns/{campaign_id}/start", response_model=CampaignOut)
async def start_campaign(
    campaign_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> CampaignOut:
    """Start a campaign immediately."""
    repo = SqlAlchemyCampaignRepository(session)
    campaign = await repo.get_by_id(campaign_id)

    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    try:
        campaign.start()
        await repo.update(campaign)
        await session.commit()

        # Queue campaign execution
        from app.infrastructure.tasks.campaign_tasks import execute_campaign
        execute_campaign.delay(campaign_id)

        return _campaign_to_out(campaign)

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/campaigns/{campaign_id}/pause", response_model=CampaignOut)
async def pause_campaign(
    campaign_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> CampaignOut:
    """Pause a running campaign."""
    repo = SqlAlchemyCampaignRepository(session)
    campaign = await repo.get_by_id(campaign_id)

    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    try:
        campaign.pause()
        await repo.update(campaign)
        await session.commit()

        return _campaign_to_out(campaign)

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/campaigns/{campaign_id}/cancel", response_model=CampaignOut)
async def cancel_campaign(
    campaign_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> CampaignOut:
    """Cancel a campaign."""
    repo = SqlAlchemyCampaignRepository(session)
    campaign = await repo.get_by_id(campaign_id)

    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    try:
        campaign.cancel()
        await repo.update(campaign)
        await session.commit()

        return _campaign_to_out(campaign)

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# Notification Preferences Endpoints
# ============================================================================


@router.get("/customers/{customer_id}/preferences", response_model=NotificationPreferencesOut)
async def get_notification_preferences(
    customer_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*SALES_ROLES)),
) -> NotificationPreferencesOut:
    """Get customer notification preferences."""
    repo = SqlAlchemyNotificationPreferencesRepository(session)
    prefs = await repo.get_or_create(customer_id)

    return NotificationPreferencesOut(
        customer_id=prefs.customer_id,
        email_enabled=prefs.email_enabled,
        sms_enabled=prefs.sms_enabled,
        push_enabled=prefs.push_enabled,
        in_app_enabled=prefs.in_app_enabled,
        transactional_enabled=prefs.transactional_enabled,
        loyalty_enabled=prefs.loyalty_enabled,
        marketing_enabled=prefs.marketing_enabled,
        engagement_enabled=prefs.engagement_enabled,
        quiet_hours_start=prefs.quiet_hours_start,
        quiet_hours_end=prefs.quiet_hours_end,
        timezone=prefs.timezone,
    )


@router.put("/customers/{customer_id}/preferences", response_model=NotificationPreferencesOut)
async def update_notification_preferences(
    customer_id: str,
    request: NotificationPreferencesRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*SALES_ROLES)),
) -> NotificationPreferencesOut:
    """Update customer notification preferences."""
    repo = SqlAlchemyNotificationPreferencesRepository(session)
    prefs = await repo.get_or_create(customer_id)

    prefs.update_channel_preferences(
        email=request.email_enabled,
        sms=request.sms_enabled,
        push=request.push_enabled,
    )

    prefs.update_category_preferences(
        marketing=request.marketing_enabled,
        loyalty=request.loyalty_enabled,
    )

    if request.quiet_hours_start is not None or request.quiet_hours_end is not None:
        prefs.set_quiet_hours(
            start_hour=request.quiet_hours_start,
            end_hour=request.quiet_hours_end,
        )

    await repo.update(prefs)
    await session.commit()

    return NotificationPreferencesOut(
        customer_id=prefs.customer_id,
        email_enabled=prefs.email_enabled,
        sms_enabled=prefs.sms_enabled,
        push_enabled=prefs.push_enabled,
        in_app_enabled=prefs.in_app_enabled,
        transactional_enabled=prefs.transactional_enabled,
        loyalty_enabled=prefs.loyalty_enabled,
        marketing_enabled=prefs.marketing_enabled,
        engagement_enabled=prefs.engagement_enabled,
        quiet_hours_start=prefs.quiet_hours_start,
        quiet_hours_end=prefs.quiet_hours_end,
        timezone=prefs.timezone,
    )


# ============================================================================
# Feedback Endpoints
# ============================================================================


@router.post("/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    request: FeedbackCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*SALES_ROLES)),
) -> FeedbackOut:
    """Create customer feedback."""
    try:
        feedback = CustomerFeedback.create(
            customer_id=request.customer_id,
            feedback_type=request.feedback_type,
            subject=request.subject,
            content=request.content,
            rating=request.rating,
            reference_id=request.reference_id,
            reference_type=request.reference_type,
        )

        repo = SqlAlchemyFeedbackRepository(session)
        await repo.save(feedback)
        await session.commit()

        return _feedback_to_out(feedback)

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/feedback", response_model=FeedbackListOut)
async def list_feedback(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
    customer_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> FeedbackListOut:
    """List customer feedback."""
    repo = SqlAlchemyFeedbackRepository(session)

    if customer_id:
        feedback_list = await repo.list_by_customer(customer_id, limit, offset)
    elif status_filter == "pending":
        feedback_list = await repo.list_pending(limit, offset)
    else:
        feedback_list = await repo.list_pending(limit, offset)  # Default to pending

    return FeedbackListOut(
        feedback=[_feedback_to_out(f) for f in feedback_list],
        total=len(feedback_list),
    )


@router.get("/feedback/{feedback_id}", response_model=FeedbackOut)
async def get_feedback(
    feedback_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> FeedbackOut:
    """Get feedback by ID."""
    repo = SqlAlchemyFeedbackRepository(session)
    feedback = await repo.get_by_id(feedback_id)

    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    return _feedback_to_out(feedback)


@router.post("/feedback/{feedback_id}/respond", response_model=FeedbackOut)
async def respond_to_feedback(
    feedback_id: str,
    request: FeedbackResponseRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> FeedbackOut:
    """Respond to customer feedback."""
    repo = SqlAlchemyFeedbackRepository(session)
    feedback = await repo.get_by_id(feedback_id)

    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    try:
        feedback.respond(request.response, responded_by="admin")  # TODO: Get actual user ID
        await repo.update(feedback)
        await session.commit()

        return _feedback_to_out(feedback)

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/feedback/{feedback_id}/resolve", response_model=FeedbackOut)
async def resolve_feedback(
    feedback_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> FeedbackOut:
    """Mark feedback as resolved."""
    repo = SqlAlchemyFeedbackRepository(session)
    feedback = await repo.get_by_id(feedback_id)

    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    feedback.resolve()
    await repo.update(feedback)
    await session.commit()

    return _feedback_to_out(feedback)


@router.post("/feedback/{feedback_id}/publish", response_model=FeedbackOut)
async def publish_feedback(
    feedback_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> FeedbackOut:
    """Mark feedback as public (for testimonials)."""
    repo = SqlAlchemyFeedbackRepository(session)
    feedback = await repo.get_by_id(feedback_id)

    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    feedback.set_public(True)
    await repo.update(feedback)
    await session.commit()

    return _feedback_to_out(feedback)


@router.get("/feedback/public/reviews", response_model=FeedbackListOut)
async def get_public_reviews(
    session: Annotated[AsyncSession, Depends(get_session)],
    min_rating: int = Query(4, ge=1, le=5),
    limit: int = Query(20, ge=1, le=50),
) -> FeedbackListOut:
    """Get public reviews for testimonials."""
    repo = SqlAlchemyFeedbackRepository(session)
    reviews = await repo.list_public_reviews(min_rating, limit)

    return FeedbackListOut(
        feedback=[_feedback_to_out(f) for f in reviews],
        total=len(reviews),
    )


# ============================================================================
# Engagement Profile Endpoints
# ============================================================================


@router.get("/customers/{customer_id}/profile", response_model=EngagementProfileOut)
async def get_engagement_profile(
    customer_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*SALES_ROLES)),
) -> EngagementProfileOut:
    """Get customer engagement profile."""
    repo = SqlAlchemyEngagementProfileRepository(session)
    profile = await repo.get_or_create(customer_id)

    return EngagementProfileOut(
        customer_id=profile.customer_id,
        segment=profile.segment.value,
        total_purchases=profile.total_purchases,
        total_spent=float(profile.total_spent),
        average_order_value=float(profile.average_order_value),
        last_purchase_at=profile.last_purchase_at,
        total_interactions=profile.total_interactions,
        email_open_rate=profile.email_open_rate,
        email_click_rate=profile.email_click_rate,
        loyalty_tier=profile.loyalty_tier,
        current_points=profile.current_points,
        lifetime_points=profile.lifetime_points,
        first_seen_at=profile.first_seen_at,
    )


@router.get("/segments", response_model=list[SegmentStatsOut])
async def get_segment_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> list[SegmentStatsOut]:
    """Get statistics for all customer segments."""
    repo = SqlAlchemyEngagementProfileRepository(session)
    stats = await repo.get_segment_stats()

    return [
        SegmentStatsOut(
            segment=segment,
            count=data["count"],
            avg_spent=data["avg_spent"],
            avg_purchases=data["avg_purchases"],
            avg_open_rate=data["avg_open_rate"],
        )
        for segment, data in stats.items()
    ]


@router.get("/dashboard", response_model=EngagementDashboardOut)
async def get_engagement_dashboard(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> EngagementDashboardOut:
    """Get engagement dashboard with summary stats."""
    profile_repo = SqlAlchemyEngagementProfileRepository(session)
    feedback_repo = SqlAlchemyFeedbackRepository(session)

    # Get segment stats
    segment_stats = await profile_repo.get_segment_stats()

    # Count by segment
    segment_counts = await profile_repo.count_by_segment()
    total_customers = sum(segment_counts.values())
    at_risk_count = segment_counts.get(CustomerSegment.AT_RISK, 0)
    vip_count = segment_counts.get(CustomerSegment.VIP, 0)

    # Feedback stats
    avg_rating = await feedback_repo.get_average_rating()
    feedback_counts = await feedback_repo.count_by_status()
    pending_feedback = feedback_counts.get("pending", 0)

    return EngagementDashboardOut(
        segment_stats=[
            SegmentStatsOut(
                segment=segment,
                count=data["count"],
                avg_spent=data["avg_spent"],
                avg_purchases=data["avg_purchases"],
                avg_open_rate=data["avg_open_rate"],
            )
            for segment, data in segment_stats.items()
        ],
        total_customers=total_customers,
        at_risk_count=at_risk_count,
        vip_count=vip_count,
        avg_rating=avg_rating,
        pending_feedback=pending_feedback,
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _campaign_to_out(campaign: MarketingCampaign) -> CampaignOut:
    """Convert campaign to output schema."""
    return CampaignOut(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        campaign_type=campaign.campaign_type.value,
        trigger=campaign.trigger.value,
        status=campaign.status.value,
        scheduled_at=campaign.scheduled_at,
        started_at=campaign.started_at,
        completed_at=campaign.completed_at,
        is_recurring=campaign.is_recurring,
        metrics=CampaignMetricsOut(
            total_targeted=campaign.metrics.total_targeted,
            total_sent=campaign.metrics.total_sent,
            total_delivered=campaign.metrics.total_delivered,
            total_opened=campaign.metrics.total_opened,
            total_clicked=campaign.metrics.total_clicked,
            total_converted=campaign.metrics.total_converted,
            total_failed=campaign.metrics.total_failed,
            revenue_generated=campaign.metrics.revenue_generated,
            delivery_rate=campaign.metrics.delivery_rate,
            open_rate=campaign.metrics.open_rate,
            click_rate=campaign.metrics.click_rate,
            conversion_rate=campaign.metrics.conversion_rate,
        ),
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


def _feedback_to_out(feedback: CustomerFeedback) -> FeedbackOut:
    """Convert feedback to output schema."""
    return FeedbackOut(
        id=feedback.id,
        customer_id=feedback.customer_id,
        feedback_type=feedback.feedback_type,
        subject=feedback.subject,
        content=feedback.content,
        rating=feedback.rating,
        reference_id=feedback.reference_id,
        reference_type=feedback.reference_type,
        status=feedback.status,
        response=feedback.response,
        responded_at=feedback.responded_at,
        is_public=feedback.is_public,
        sentiment_score=feedback.sentiment_score,
        created_at=feedback.created_at,
    )
