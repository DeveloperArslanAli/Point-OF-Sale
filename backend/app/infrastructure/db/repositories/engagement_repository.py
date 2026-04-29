"""Repository implementations for customer engagement tracking."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.customers.engagement import (
    CustomerEngagementProfile,
    CustomerSegment,
    EngagementEvent,
    EngagementEventType,
)
from app.infrastructure.db.models.engagement_model import (
    CustomerEngagementProfileModel,
    EngagementEventModel,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

from app.core.tenant import get_current_tenant_id


class SqlAlchemyEngagementEventRepository:
    """Repository for engagement events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id and hasattr(EngagementEventModel, "tenant_id"):
            return stmt.where(EngagementEventModel.tenant_id == tenant_id)
        return stmt

    async def save(self, event: EngagementEvent) -> None:
        """Save an engagement event."""
        tenant_id = get_current_tenant_id()
        model = EngagementEventModel(
            id=event.id,
            customer_id=event.customer_id,
            event_type=event.event_type,
            reference_id=event.reference_id,
            metadata_json=event.metadata,
            created_at=event.created_at,
            tenant_id=tenant_id,
        )
        self._session.add(model)
        await self._session.flush()

    async def save_many(self, events: list[EngagementEvent]) -> None:
        """Save multiple events."""
        tenant_id = get_current_tenant_id()
        models = [
            EngagementEventModel(
                id=e.id,
                customer_id=e.customer_id,
                event_type=e.event_type,
                reference_id=e.reference_id,
                metadata_json=e.metadata,
                created_at=e.created_at,
                tenant_id=tenant_id,
            )
            for e in events
        ]
        self._session.add_all(models)
        await self._session.flush()

    async def get_by_id(self, event_id: str) -> EngagementEvent | None:
        """Get event by ID."""
        stmt = select(EngagementEventModel).where(EngagementEventModel.id == event_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_customer(
        self,
        customer_id: str,
        event_types: list[EngagementEventType] | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EngagementEvent]:
        """List events for a customer."""
        query = select(EngagementEventModel).where(
            EngagementEventModel.customer_id == customer_id
        )
        query = self._apply_tenant_filter(query)

        if event_types:
            query = query.where(EngagementEventModel.event_type.in_(event_types))
        if since:
            query = query.where(EngagementEventModel.created_at >= since)

        query = query.order_by(EngagementEventModel.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_type(
        self,
        customer_id: str,
        event_type: EngagementEventType,
        since: datetime | None = None,
    ) -> int:
        """Count events of a type for a customer."""
        query = select(func.count(EngagementEventModel.id)).where(
            and_(
                EngagementEventModel.customer_id == customer_id,
                EngagementEventModel.event_type == event_type,
            )
        )
        if since:
            query = query.where(EngagementEventModel.created_at >= since)

        result = await self._session.execute(query)
        return result.scalar() or 0

    async def get_recent_event_types(
        self,
        customer_id: str,
        days: int = 30,
    ) -> dict[EngagementEventType, int]:
        """Get event type counts for last N days."""
        since = datetime.now(UTC) - timedelta(days=days)
        result = await self._session.execute(
            select(
                EngagementEventModel.event_type,
                func.count(EngagementEventModel.id),
            )
            .where(
                and_(
                    EngagementEventModel.customer_id == customer_id,
                    EngagementEventModel.created_at >= since,
                )
            )
            .group_by(EngagementEventModel.event_type)
        )
        return {row[0]: row[1] for row in result.all()}

    async def get_customers_by_event(
        self,
        event_type: EngagementEventType,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Sequence[str]:
        """Get distinct customer IDs who had a specific event."""
        query = select(EngagementEventModel.customer_id.distinct()).where(
            EngagementEventModel.event_type == event_type
        )
        if since:
            query = query.where(EngagementEventModel.created_at >= since)
        if until:
            query = query.where(EngagementEventModel.created_at <= until)

        result = await self._session.execute(query)
        return [row[0] for row in result.all()]

    def _to_entity(self, model: EngagementEventModel) -> EngagementEvent:
        """Convert model to entity."""
        return EngagementEvent(
            id=model.id,
            customer_id=model.customer_id,
            event_type=model.event_type,
            reference_id=model.reference_id,
            metadata=dict(model.metadata_json) if model.metadata_json else {},
            created_at=model.created_at,
        )


class SqlAlchemyEngagementProfileRepository:
    """Repository for customer engagement profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, profile: CustomerEngagementProfile) -> None:
        """Save an engagement profile."""
        model = CustomerEngagementProfileModel(
            id=profile.id,
            customer_id=profile.customer_id,
            segment=profile.segment,
            total_purchases=profile.total_purchases,
            total_spent=profile.total_spent,
            average_order_value=profile.average_order_value,
            last_purchase_at=profile.last_purchase_at,
            total_interactions=profile.total_interactions,
            last_interaction_at=profile.last_interaction_at,
            email_open_rate=profile.email_open_rate,
            email_click_rate=profile.email_click_rate,
            loyalty_tier=profile.loyalty_tier,
            current_points=profile.current_points,
            lifetime_points=profile.lifetime_points,
            first_seen_at=profile.first_seen_at,
            updated_at=profile.updated_at,
            version=profile.version,
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, profile: CustomerEngagementProfile) -> None:
        """Update an engagement profile."""
        await self._session.execute(
            update(CustomerEngagementProfileModel)
            .where(CustomerEngagementProfileModel.id == profile.id)
            .values(
                segment=profile.segment,
                total_purchases=profile.total_purchases,
                total_spent=profile.total_spent,
                average_order_value=profile.average_order_value,
                last_purchase_at=profile.last_purchase_at,
                total_interactions=profile.total_interactions,
                last_interaction_at=profile.last_interaction_at,
                email_open_rate=profile.email_open_rate,
                email_click_rate=profile.email_click_rate,
                loyalty_tier=profile.loyalty_tier,
                current_points=profile.current_points,
                lifetime_points=profile.lifetime_points,
                updated_at=profile.updated_at,
                version=profile.version,
            )
        )

    async def get_by_id(self, profile_id: str) -> CustomerEngagementProfile | None:
        """Get profile by ID."""
        result = await self._session.execute(
            select(CustomerEngagementProfileModel).where(
                CustomerEngagementProfileModel.id == profile_id
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_customer_id(
        self,
        customer_id: str,
    ) -> CustomerEngagementProfile | None:
        """Get profile by customer ID."""
        result = await self._session.execute(
            select(CustomerEngagementProfileModel).where(
                CustomerEngagementProfileModel.customer_id == customer_id
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_or_create(self, customer_id: str) -> CustomerEngagementProfile:
        """Get existing profile or create a new one."""
        existing = await self.get_by_customer_id(customer_id)
        if existing:
            return existing

        profile = CustomerEngagementProfile.create(customer_id=customer_id)
        await self.save(profile)
        return profile

    async def list_by_segment(
        self,
        segment: CustomerSegment,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[CustomerEngagementProfile]:
        """List profiles by segment."""
        result = await self._session.execute(
            select(CustomerEngagementProfileModel)
            .where(CustomerEngagementProfileModel.segment == segment)
            .order_by(CustomerEngagementProfileModel.total_spent.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_at_risk_customers(
        self,
        inactive_days: int = 60,
        limit: int = 100,
    ) -> Sequence[CustomerEngagementProfile]:
        """List customers who haven't purchased recently."""
        cutoff = datetime.now(UTC) - timedelta(days=inactive_days)
        result = await self._session.execute(
            select(CustomerEngagementProfileModel)
            .where(
                and_(
                    CustomerEngagementProfileModel.last_purchase_at.isnot(None),
                    CustomerEngagementProfileModel.last_purchase_at < cutoff,
                    CustomerEngagementProfileModel.segment.notin_(
                        [CustomerSegment.CHURNED]
                    ),
                )
            )
            .order_by(CustomerEngagementProfileModel.total_spent.desc())
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_vip_customers(
        self,
        min_spent: Decimal = Decimal("1000"),
        limit: int = 100,
    ) -> Sequence[CustomerEngagementProfile]:
        """List VIP customers by total spent."""
        result = await self._session.execute(
            select(CustomerEngagementProfileModel)
            .where(CustomerEngagementProfileModel.total_spent >= min_spent)
            .order_by(CustomerEngagementProfileModel.total_spent.desc())
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_segment(self) -> dict[CustomerSegment, int]:
        """Count profiles by segment."""
        result = await self._session.execute(
            select(
                CustomerEngagementProfileModel.segment,
                func.count(CustomerEngagementProfileModel.id),
            ).group_by(CustomerEngagementProfileModel.segment)
        )
        return {row[0]: row[1] for row in result.all()}

    async def get_segment_stats(self) -> dict[str, dict]:
        """Get aggregated stats per segment."""
        result = await self._session.execute(
            select(
                CustomerEngagementProfileModel.segment,
                func.count(CustomerEngagementProfileModel.id),
                func.avg(CustomerEngagementProfileModel.total_spent),
                func.avg(CustomerEngagementProfileModel.total_purchases),
                func.avg(CustomerEngagementProfileModel.email_open_rate),
            ).group_by(CustomerEngagementProfileModel.segment)
        )
        return {
            row[0].value: {
                "count": row[1],
                "avg_spent": float(row[2]) if row[2] else 0.0,
                "avg_purchases": float(row[3]) if row[3] else 0.0,
                "avg_open_rate": float(row[4]) if row[4] else 0.0,
            }
            for row in result.all()
        }

    def _to_entity(
        self,
        model: CustomerEngagementProfileModel,
    ) -> CustomerEngagementProfile:
        """Convert model to entity."""
        return CustomerEngagementProfile(
            id=model.id,
            customer_id=model.customer_id,
            segment=model.segment,
            total_purchases=model.total_purchases,
            total_spent=model.total_spent,
            average_order_value=model.average_order_value,
            last_purchase_at=model.last_purchase_at,
            total_interactions=model.total_interactions,
            last_interaction_at=model.last_interaction_at,
            email_open_rate=model.email_open_rate,
            email_click_rate=model.email_click_rate,
            loyalty_tier=model.loyalty_tier,
            current_points=model.current_points,
            lifetime_points=model.lifetime_points,
            first_seen_at=model.first_seen_at,
            updated_at=model.updated_at,
            version=model.version,
        )
