"""Gift card repository implementation."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.gift_cards.ports import IGiftCardRepository
from app.core.tenant import get_current_tenant_id
from app.domain.common.money import Money
from app.domain.gift_cards.entities import GiftCard, GiftCardStatus
from app.infrastructure.db.models.gift_card_model import GiftCardModel


class SqlAlchemyGiftCardRepository(IGiftCardRepository):
    """SQLAlchemy implementation of gift card repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id and hasattr(GiftCardModel, "tenant_id"):
            return stmt.where(GiftCardModel.tenant_id == tenant_id)
        return stmt

    async def add(self, gift_card: GiftCard) -> None:
        """Add a new gift card."""
        model = self._to_model(gift_card)
        model.tenant_id = get_current_tenant_id()
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, gift_card_id: str) -> GiftCard | None:
        """Get a gift card by ID."""
        stmt = select(GiftCardModel).where(GiftCardModel.id == gift_card_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_code(self, code: str) -> GiftCard | None:
        """Get a gift card by its redemption code."""
        stmt = select(GiftCardModel).where(GiftCardModel.code == code)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, gift_card: GiftCard) -> None:
        """Update an existing gift card."""
        stmt = select(GiftCardModel).where(GiftCardModel.id == gift_card.id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if not model:
            msg = f"Gift card {gift_card.id} not found"
            raise ValueError(msg)
        
        # Update fields
        model.code = gift_card.code
        model.initial_balance = gift_card.initial_balance.amount
        model.current_balance = gift_card.current_balance.amount
        model.currency = gift_card.currency
        model.status = gift_card.status.value
        model.issued_date = gift_card.issued_date
        model.expiry_date = gift_card.expiry_date
        model.customer_id = gift_card.customer_id
        model.updated_at = gift_card.updated_at
        model.version = gift_card.version
        
        await self._session.flush()

    async def list_by_customer(
        self,
        customer_id: str,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[GiftCard], int]:
        """List gift cards for a customer."""
        # Count total
        count_stmt = (
            select(func.count())
            .select_from(GiftCardModel)
            .where(GiftCardModel.customer_id == customer_id)
        )
        count_stmt = self._apply_tenant_filter(count_stmt)
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get page
        offset = (page - 1) * limit
        stmt = (
            select(GiftCardModel)
            .where(GiftCardModel.customer_id == customer_id)
            .order_by(GiftCardModel.issued_date.desc())
            .offset(offset)
            .limit(limit)
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        
        entities = [self._to_entity(model) for model in models]
        return entities, total

    def _to_entity(self, model: GiftCardModel) -> GiftCard:
        """Convert model to entity."""
        return GiftCard(
            id=model.id,
            code=model.code,
            initial_balance=Money(Decimal(str(model.initial_balance)), currency=model.currency),
            current_balance=Money(Decimal(str(model.current_balance)), currency=model.currency),
            status=GiftCardStatus(model.status),
            issued_date=model.issued_date,
            expiry_date=model.expiry_date,
            customer_id=model.customer_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, entity: GiftCard) -> GiftCardModel:
        """Convert entity to model."""
        return GiftCardModel(
            id=entity.id,
            code=entity.code,
            initial_balance=entity.initial_balance.amount,
            current_balance=entity.current_balance.amount,
            currency=entity.currency,
            status=entity.status.value,
            issued_date=entity.issued_date,
            expiry_date=entity.expiry_date,
            customer_id=entity.customer_id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            version=entity.version,
        )
