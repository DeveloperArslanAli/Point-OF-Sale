"""SQLAlchemy repository for customer loyalty program."""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import get_current_tenant_id
from app.domain.customers.loyalty import (
    LoyaltyAccount,
    LoyaltyPointTransaction,
    LoyaltyTier,
    PointTransactionType,
)
from app.infrastructure.db.models.loyalty_model import (
    LoyaltyAccountModel,
    LoyaltyPointTransactionModel,
)


class SqlAlchemyLoyaltyAccountRepository:
    """SQLAlchemy implementation of loyalty account repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(LoyaltyAccountModel.tenant_id == tenant_id)
        return stmt

    def _to_domain(self, model: LoyaltyAccountModel) -> LoyaltyAccount:
        """Convert model to domain entity."""
        return LoyaltyAccount(
            id=model.id,
            customer_id=model.customer_id,
            current_points=model.current_points,
            lifetime_points=model.lifetime_points,
            tier=LoyaltyTier(model.tier.value if hasattr(model.tier, 'value') else model.tier),
            enrolled_at=model.enrolled_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, entity: LoyaltyAccount) -> LoyaltyAccountModel:
        """Convert domain entity to model."""
        return LoyaltyAccountModel(
            id=entity.id,
            customer_id=entity.customer_id,
            current_points=entity.current_points,
            lifetime_points=entity.lifetime_points,
            tier=entity.tier,
            enrolled_at=entity.enrolled_at,
            updated_at=entity.updated_at,
            version=entity.version,
            tenant_id=get_current_tenant_id(),
        )

    async def add(self, account: LoyaltyAccount) -> None:
        """Add a new loyalty account."""
        model = self._to_model(account)
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, account_id: str) -> LoyaltyAccount | None:
        """Get loyalty account by ID."""
        stmt = select(LoyaltyAccountModel).where(LoyaltyAccountModel.id == account_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_customer_id(self, customer_id: str) -> LoyaltyAccount | None:
        """Get loyalty account by customer ID."""
        stmt = select(LoyaltyAccountModel).where(
            LoyaltyAccountModel.customer_id == customer_id
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def update(
        self, account: LoyaltyAccount, *, expected_version: int
    ) -> bool:
        """Update loyalty account with optimistic locking."""
        stmt = select(LoyaltyAccountModel).where(
            LoyaltyAccountModel.id == account.id,
            LoyaltyAccountModel.version == expected_version,
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return False

        model.current_points = account.current_points
        model.lifetime_points = account.lifetime_points
        model.tier = account.tier
        model.updated_at = account.updated_at
        model.version = account.version

        await self._session.flush()
        return True

    async def list_by_tier(
        self,
        tier: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[LoyaltyAccount], int]:
        """List loyalty accounts by tier."""
        base_stmt = select(LoyaltyAccountModel).where(
            LoyaltyAccountModel.tier == LoyaltyTier(tier)
        )
        base_stmt = self._apply_tenant_filter(base_stmt)

        # Count query
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Data query
        stmt = base_stmt.offset(offset).limit(limit).order_by(
            LoyaltyAccountModel.lifetime_points.desc()
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(m) for m in models], total


class SqlAlchemyLoyaltyTransactionRepository:
    """SQLAlchemy implementation of loyalty transaction repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(LoyaltyPointTransactionModel.tenant_id == tenant_id)
        return stmt

    def _to_domain(self, model: LoyaltyPointTransactionModel) -> LoyaltyPointTransaction:
        """Convert model to domain entity."""
        return LoyaltyPointTransaction(
            id=model.id,
            loyalty_account_id=model.loyalty_account_id,
            transaction_type=PointTransactionType(
                model.transaction_type.value
                if hasattr(model.transaction_type, 'value')
                else model.transaction_type
            ),
            points=model.points,
            balance_after=model.balance_after,
            reference_id=model.reference_id,
            description=model.description,
            created_at=model.created_at,
        )

    def _to_model(self, entity: LoyaltyPointTransaction) -> LoyaltyPointTransactionModel:
        """Convert domain entity to model."""
        return LoyaltyPointTransactionModel(
            id=entity.id,
            loyalty_account_id=entity.loyalty_account_id,
            transaction_type=entity.transaction_type,
            points=entity.points,
            balance_after=entity.balance_after,
            reference_id=entity.reference_id,
            description=entity.description,
            created_at=entity.created_at,
            tenant_id=get_current_tenant_id(),
        )

    async def add(self, transaction: LoyaltyPointTransaction) -> None:
        """Add a new point transaction."""
        model = self._to_model(transaction)
        self._session.add(model)
        await self._session.flush()

    async def list_by_account(
        self,
        account_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[LoyaltyPointTransaction], int]:
        """List transactions for an account."""
        base_stmt = select(LoyaltyPointTransactionModel).where(
            LoyaltyPointTransactionModel.loyalty_account_id == account_id
        )
        base_stmt = self._apply_tenant_filter(base_stmt)

        # Count query
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Data query
        stmt = base_stmt.offset(offset).limit(limit).order_by(
            LoyaltyPointTransactionModel.created_at.desc()
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(m) for m in models], total

    async def list_by_reference(
        self,
        reference_id: str,
    ) -> Sequence[LoyaltyPointTransaction]:
        """List transactions by reference ID (e.g., sale ID)."""
        stmt = select(LoyaltyPointTransactionModel).where(
            LoyaltyPointTransactionModel.reference_id == reference_id
        )
        stmt = self._apply_tenant_filter(stmt)
        stmt = stmt.order_by(LoyaltyPointTransactionModel.created_at.desc())
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(m) for m in models]
