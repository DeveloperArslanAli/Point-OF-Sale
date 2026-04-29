"""Repository implementations for marketing campaigns and feedback."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import get_current_tenant_id
from app.domain.customers.campaigns import (
    CampaignContent,
    CampaignMetrics,
    CampaignRecipient,
    CampaignStatus,
    CampaignTargeting,
    CampaignTrigger,
    CampaignType,
    CustomerFeedback,
    MarketingCampaign,
    TargetingCriteria,
)
from app.domain.customers.engagement import CustomerSegment
from app.infrastructure.db.models.campaign_model import (
    CampaignRecipientModel,
    CustomerFeedbackModel,
    MarketingCampaignModel,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class SqlAlchemyCampaignRepository:
    """Repository for marketing campaigns."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt: Select[Any]) -> Select[Any]:
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(MarketingCampaignModel.tenant_id == tenant_id)
        return stmt

    async def save(self, campaign: MarketingCampaign) -> None:
        """Save a campaign."""
        model = MarketingCampaignModel(
            id=campaign.id,
            tenant_id=get_current_tenant_id(),
            name=campaign.name,
            description=campaign.description,
            campaign_type=campaign.campaign_type,
            trigger=campaign.trigger,
            status=campaign.status,
            targeting_json=self._targeting_to_dict(campaign.targeting),
            content_json=self._content_to_dict(campaign.content),
            metrics_json=self._metrics_to_dict(campaign.metrics),
            scheduled_at=campaign.scheduled_at,
            started_at=campaign.started_at,
            completed_at=campaign.completed_at,
            send_rate_limit=campaign.send_rate_limit,
            is_recurring=campaign.is_recurring,
            recurrence_pattern=campaign.recurrence_pattern,
            created_by=campaign.created_by,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
            version=campaign.version,
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, campaign: MarketingCampaign) -> None:
        """Update a campaign."""
        tenant_id = get_current_tenant_id()
        stmt = update(MarketingCampaignModel).where(MarketingCampaignModel.id == campaign.id)
        if tenant_id:
            stmt = stmt.where(MarketingCampaignModel.tenant_id == tenant_id)
        await self._session.execute(
            stmt.values(
                name=campaign.name,
                description=campaign.description,
                campaign_type=campaign.campaign_type,
                trigger=campaign.trigger,
                status=campaign.status,
                targeting_json=self._targeting_to_dict(campaign.targeting),
                content_json=self._content_to_dict(campaign.content),
                metrics_json=self._metrics_to_dict(campaign.metrics),
                scheduled_at=campaign.scheduled_at,
                started_at=campaign.started_at,
                completed_at=campaign.completed_at,
                send_rate_limit=campaign.send_rate_limit,
                is_recurring=campaign.is_recurring,
                recurrence_pattern=campaign.recurrence_pattern,
                updated_at=campaign.updated_at,
                version=campaign.version,
            )
        )

    async def get_by_id(self, campaign_id: str) -> MarketingCampaign | None:
        """Get campaign by ID."""
        stmt = select(MarketingCampaignModel).where(
            MarketingCampaignModel.id == campaign_id
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_status(
        self,
        status: CampaignStatus | None = None,
        campaign_type: CampaignType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[MarketingCampaign]:
        """List campaigns by status."""
        query = select(MarketingCampaignModel)
        query = self._apply_tenant_filter(query)

        if status:
            query = query.where(MarketingCampaignModel.status == status)
        if campaign_type:
            query = query.where(MarketingCampaignModel.campaign_type == campaign_type)

        query = query.order_by(MarketingCampaignModel.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_scheduled_to_run(self) -> Sequence[MarketingCampaign]:
        """Get campaigns scheduled to run now."""
        now = datetime.now(UTC)
        stmt = select(MarketingCampaignModel).where(
            and_(
                MarketingCampaignModel.status == CampaignStatus.SCHEDULED,
                MarketingCampaignModel.scheduled_at <= now,
            )
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_trigger(
        self,
        trigger: CampaignTrigger,
        active_only: bool = True,
    ) -> Sequence[MarketingCampaign]:
        """Get campaigns by trigger type."""
        query = select(MarketingCampaignModel).where(
            MarketingCampaignModel.trigger == trigger
        )
        query = self._apply_tenant_filter(query)
        if active_only:
            query = query.where(
                MarketingCampaignModel.status.in_(
                    [CampaignStatus.DRAFT, CampaignStatus.SCHEDULED, CampaignStatus.RUNNING]
                )
            )

        result = await self._session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_status(self) -> dict[CampaignStatus, int]:
        """Count campaigns by status."""
        stmt = select(
            MarketingCampaignModel.status,
            func.count(MarketingCampaignModel.id),
        ).group_by(MarketingCampaignModel.status)
        tenant_id = get_current_tenant_id()
        if tenant_id:
            stmt = stmt.where(MarketingCampaignModel.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    def _targeting_to_dict(self, targeting: CampaignTargeting) -> dict:
        """Convert targeting to dict for JSON storage."""
        return {
            "criteria": targeting.criteria.value,
            "segments": [s.value for s in targeting.segments],
            "loyalty_tiers": targeting.loyalty_tiers,
            "min_purchase_count": targeting.min_purchase_count,
            "min_total_spent": targeting.min_total_spent,
            "max_total_spent": targeting.max_total_spent,
            "custom_customer_ids": targeting.custom_customer_ids,
            "exclude_customer_ids": targeting.exclude_customer_ids,
        }

    def _content_to_dict(self, content: CampaignContent) -> dict:
        """Convert content to dict for JSON storage."""
        return {
            "subject": content.subject,
            "body": content.body,
            "html_body": content.html_body,
            "call_to_action": content.call_to_action,
            "discount_code": content.discount_code,
            "template_id": content.template_id,
        }

    def _metrics_to_dict(self, metrics: CampaignMetrics) -> dict:
        """Convert metrics to dict for JSON storage."""
        return {
            "total_targeted": metrics.total_targeted,
            "total_sent": metrics.total_sent,
            "total_delivered": metrics.total_delivered,
            "total_opened": metrics.total_opened,
            "total_clicked": metrics.total_clicked,
            "total_converted": metrics.total_converted,
            "total_unsubscribed": metrics.total_unsubscribed,
            "total_bounced": metrics.total_bounced,
            "total_failed": metrics.total_failed,
            "revenue_generated": metrics.revenue_generated,
        }

    def _dict_to_targeting(self, data: dict) -> CampaignTargeting:
        """Convert dict to targeting."""
        return CampaignTargeting(
            criteria=TargetingCriteria(data.get("criteria", "all_customers")),
            segments=[CustomerSegment(s) for s in data.get("segments", [])],
            loyalty_tiers=data.get("loyalty_tiers", []),
            min_purchase_count=data.get("min_purchase_count"),
            min_total_spent=data.get("min_total_spent"),
            max_total_spent=data.get("max_total_spent"),
            custom_customer_ids=data.get("custom_customer_ids", []),
            exclude_customer_ids=data.get("exclude_customer_ids", []),
        )

    def _dict_to_content(self, data: dict) -> CampaignContent:
        """Convert dict to content."""
        return CampaignContent(
            subject=data.get("subject"),
            body=data.get("body", ""),
            html_body=data.get("html_body"),
            call_to_action=data.get("call_to_action"),
            discount_code=data.get("discount_code"),
            template_id=data.get("template_id"),
        )

    def _dict_to_metrics(self, data: dict) -> CampaignMetrics:
        """Convert dict to metrics."""
        return CampaignMetrics(
            total_targeted=data.get("total_targeted", 0),
            total_sent=data.get("total_sent", 0),
            total_delivered=data.get("total_delivered", 0),
            total_opened=data.get("total_opened", 0),
            total_clicked=data.get("total_clicked", 0),
            total_converted=data.get("total_converted", 0),
            total_unsubscribed=data.get("total_unsubscribed", 0),
            total_bounced=data.get("total_bounced", 0),
            total_failed=data.get("total_failed", 0),
            revenue_generated=data.get("revenue_generated", 0.0),
        )

    def _to_entity(self, model: MarketingCampaignModel) -> MarketingCampaign:
        """Convert model to entity."""
        return MarketingCampaign(
            id=model.id,
            name=model.name,
            description=model.description,
            campaign_type=CampaignType(model.campaign_type),
            trigger=CampaignTrigger(model.trigger),
            status=CampaignStatus(model.status),
            targeting=self._dict_to_targeting(model.targeting_json or {}),
            content=self._dict_to_content(model.content_json or {}),
            metrics=self._dict_to_metrics(model.metrics_json or {}),
            scheduled_at=model.scheduled_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            send_rate_limit=model.send_rate_limit,
            is_recurring=model.is_recurring,
            recurrence_pattern=model.recurrence_pattern,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )


class SqlAlchemyCampaignRecipientRepository:
    """Repository for campaign recipients."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, recipient: CampaignRecipient) -> None:
        """Save a recipient."""
        model = CampaignRecipientModel(
            id=recipient.id,
            campaign_id=recipient.campaign_id,
            customer_id=recipient.customer_id,
            notification_id=recipient.notification_id,
            status=recipient.status,
            sent_at=recipient.sent_at,
            opened_at=recipient.opened_at,
            clicked_at=recipient.clicked_at,
            converted_at=recipient.converted_at,
            conversion_value=recipient.conversion_value,
            created_at=recipient.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def save_many(self, recipients: list[CampaignRecipient]) -> None:
        """Save multiple recipients."""
        models = [
            CampaignRecipientModel(
                id=r.id,
                campaign_id=r.campaign_id,
                customer_id=r.customer_id,
                notification_id=r.notification_id,
                status=r.status,
                sent_at=r.sent_at,
                opened_at=r.opened_at,
                clicked_at=r.clicked_at,
                converted_at=r.converted_at,
                conversion_value=r.conversion_value,
                created_at=r.created_at,
            )
            for r in recipients
        ]
        self._session.add_all(models)
        await self._session.flush()

    async def update(self, recipient: CampaignRecipient) -> None:
        """Update a recipient."""
        await self._session.execute(
            update(CampaignRecipientModel)
            .where(CampaignRecipientModel.id == recipient.id)
            .values(
                notification_id=recipient.notification_id,
                status=recipient.status,
                sent_at=recipient.sent_at,
                opened_at=recipient.opened_at,
                clicked_at=recipient.clicked_at,
                converted_at=recipient.converted_at,
                conversion_value=recipient.conversion_value,
            )
        )

    async def get_by_campaign(
        self,
        campaign_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[CampaignRecipient]:
        """Get recipients for a campaign."""
        query = select(CampaignRecipientModel).where(
            CampaignRecipientModel.campaign_id == campaign_id
        )
        if status:
            query = query.where(CampaignRecipientModel.status == status)

        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_pending_for_campaign(
        self,
        campaign_id: str,
        limit: int = 100,
    ) -> Sequence[CampaignRecipient]:
        """Get pending recipients for a campaign."""
        result = await self._session.execute(
            select(CampaignRecipientModel)
            .where(
                and_(
                    CampaignRecipientModel.campaign_id == campaign_id,
                    CampaignRecipientModel.status == "pending",
                )
            )
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_status(self, campaign_id: str) -> dict[str, int]:
        """Count recipients by status for a campaign."""
        result = await self._session.execute(
            select(
                CampaignRecipientModel.status,
                func.count(CampaignRecipientModel.id),
            )
            .where(CampaignRecipientModel.campaign_id == campaign_id)
            .group_by(CampaignRecipientModel.status)
        )
        return {row[0]: row[1] for row in result.all()}

    def _to_entity(self, model: CampaignRecipientModel) -> CampaignRecipient:
        """Convert model to entity."""
        return CampaignRecipient(
            id=model.id,
            campaign_id=model.campaign_id,
            customer_id=model.customer_id,
            notification_id=model.notification_id,
            status=model.status,
            sent_at=model.sent_at,
            opened_at=model.opened_at,
            clicked_at=model.clicked_at,
            converted_at=model.converted_at,
            conversion_value=model.conversion_value,
            created_at=model.created_at,
        )


class SqlAlchemyFeedbackRepository:
    """Repository for customer feedback."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, feedback: CustomerFeedback) -> None:
        """Save feedback."""
        model = CustomerFeedbackModel(
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
            responded_by=feedback.responded_by,
            is_public=feedback.is_public,
            sentiment_score=feedback.sentiment_score,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at,
            version=feedback.version,
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, feedback: CustomerFeedback) -> None:
        """Update feedback."""
        await self._session.execute(
            update(CustomerFeedbackModel)
            .where(CustomerFeedbackModel.id == feedback.id)
            .values(
                status=feedback.status,
                response=feedback.response,
                responded_at=feedback.responded_at,
                responded_by=feedback.responded_by,
                is_public=feedback.is_public,
                sentiment_score=feedback.sentiment_score,
                updated_at=feedback.updated_at,
                version=feedback.version,
            )
        )

    async def get_by_id(self, feedback_id: str) -> CustomerFeedback | None:
        """Get feedback by ID."""
        result = await self._session.execute(
            select(CustomerFeedbackModel).where(
                CustomerFeedbackModel.id == feedback_id
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_customer(
        self,
        customer_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[CustomerFeedback]:
        """List feedback by customer."""
        result = await self._session.execute(
            select(CustomerFeedbackModel)
            .where(CustomerFeedbackModel.customer_id == customer_id)
            .order_by(CustomerFeedbackModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_pending(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[CustomerFeedback]:
        """List pending feedback for review."""
        result = await self._session.execute(
            select(CustomerFeedbackModel)
            .where(CustomerFeedbackModel.status == "pending")
            .order_by(CustomerFeedbackModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_public_reviews(
        self,
        min_rating: int = 4,
        limit: int = 20,
    ) -> Sequence[CustomerFeedback]:
        """List public reviews for testimonials."""
        result = await self._session.execute(
            select(CustomerFeedbackModel)
            .where(
                and_(
                    CustomerFeedbackModel.is_public == True,  # noqa: E712
                    CustomerFeedbackModel.rating >= min_rating,
                )
            )
            .order_by(CustomerFeedbackModel.created_at.desc())
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_average_rating(
        self,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> float:
        """Get average rating, optionally filtered."""
        query = select(func.avg(CustomerFeedbackModel.rating)).where(
            CustomerFeedbackModel.rating.isnot(None)
        )
        if reference_type:
            query = query.where(CustomerFeedbackModel.reference_type == reference_type)
        if reference_id:
            query = query.where(CustomerFeedbackModel.reference_id == reference_id)

        result = await self._session.execute(query)
        avg = result.scalar()
        return float(avg) if avg else 0.0

    async def count_by_status(self) -> dict[str, int]:
        """Count feedback by status."""
        result = await self._session.execute(
            select(
                CustomerFeedbackModel.status,
                func.count(CustomerFeedbackModel.id),
            ).group_by(CustomerFeedbackModel.status)
        )
        return {row[0]: row[1] for row in result.all()}

    async def get_sentiment_summary(self) -> dict[str, int]:
        """Get sentiment summary (positive/neutral/negative counts)."""
        result = await self._session.execute(
            select(
                func.count(CustomerFeedbackModel.id).filter(
                    CustomerFeedbackModel.sentiment_score > 0.2
                ).label("positive"),
                func.count(CustomerFeedbackModel.id).filter(
                    and_(
                        CustomerFeedbackModel.sentiment_score >= -0.2,
                        CustomerFeedbackModel.sentiment_score <= 0.2,
                    )
                ).label("neutral"),
                func.count(CustomerFeedbackModel.id).filter(
                    CustomerFeedbackModel.sentiment_score < -0.2
                ).label("negative"),
            ).where(CustomerFeedbackModel.sentiment_score.isnot(None))
        )
        row = result.one()
        return {
            "positive": row[0] or 0,
            "neutral": row[1] or 0,
            "negative": row[2] or 0,
        }

    def _to_entity(self, model: CustomerFeedbackModel) -> CustomerFeedback:
        """Convert model to entity."""
        return CustomerFeedback(
            id=model.id,
            customer_id=model.customer_id,
            feedback_type=model.feedback_type,
            subject=model.subject,
            content=model.content,
            rating=model.rating,
            reference_id=model.reference_id,
            reference_type=model.reference_type,
            status=model.status,
            response=model.response,
            responded_at=model.responded_at,
            responded_by=model.responded_by,
            is_public=model.is_public,
            sentiment_score=model.sentiment_score,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )
