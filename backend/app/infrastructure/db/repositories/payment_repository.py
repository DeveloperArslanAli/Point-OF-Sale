"""
SQLAlchemy repository for Payment entities.
"""

from typing import Any, Optional

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.application.payments.ports import IPaymentRepository
from app.core.tenant import get_current_tenant_id
from app.domain.common.money import Money
from app.domain.payments.entities import (
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from app.infrastructure.db.models.payment_model import PaymentModel


class PaymentRepository(IPaymentRepository):
    """SQLAlchemy-based payment repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _apply_tenant_filter(self, stmt: Select[Any]) -> Select[Any]:
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(PaymentModel.tenant_id == tenant_id)
        return stmt

    async def add(self, payment: Payment) -> None:
        """Persist a new payment."""
        model = self._to_model(payment)
        model.tenant_id = get_current_tenant_id()
        self._session.add(model)

    async def get_by_id(self, payment_id: str) -> Optional[Payment]:
        """Find payment by ID."""
        stmt = (
            select(PaymentModel)
            .where(PaymentModel.id == payment_id)
            .options(joinedload(PaymentModel.sale))
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_sale_id(self, sale_id: str) -> list[Payment]:
        """Find all payments for a sale."""
        stmt = (
            select(PaymentModel)
            .where(PaymentModel.sale_id == sale_id)
            .order_by(PaymentModel.created_at)
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def update(self, payment: Payment) -> None:
        """Update an existing payment."""
        stmt = select(PaymentModel).where(PaymentModel.id == payment.id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        
        # Update fields from entity
        model.status = payment.status.value
        model.provider_transaction_id = payment.provider_transaction_id
        model.provider_metadata = payment.provider_metadata
        model.card_last4 = payment.card_last4
        model.card_brand = payment.card_brand
        model.authorized_at = payment.authorized_at
        model.captured_at = payment.captured_at
        model.refunded_amount = payment.refunded_amount.amount
        model.refunded_at = payment.refunded_at
        model.notes = payment.notes
        model.version = payment.version

    async def get_by_provider_transaction_id(
        self,
        provider_transaction_id: str,
    ) -> Optional[Payment]:
        """Find payment by provider transaction ID."""
        stmt = (
            select(PaymentModel)
            .where(PaymentModel.provider_transaction_id == provider_transaction_id)
            .options(joinedload(PaymentModel.sale))
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    @staticmethod
    def _to_model(entity: Payment) -> PaymentModel:
        """Convert Payment entity to ORM model."""
        return PaymentModel(
            id=entity.id,
            sale_id=entity.sale_id,
            method=entity.method.value,
            amount=entity.amount.amount,
            currency=entity.amount.currency,
            status=entity.status.value,
            provider=entity.provider.value,
            provider_transaction_id=entity.provider_transaction_id,
            provider_metadata=entity.provider_metadata,
            card_last4=entity.card_last4,
            card_brand=entity.card_brand,
            authorized_at=entity.authorized_at,
            captured_at=entity.captured_at,
            refunded_amount=entity.refunded_amount.amount,
            refunded_at=entity.refunded_at,
            created_at=entity.created_at,
            created_by=entity.created_by,
            notes=entity.notes,
            version=entity.version,
        )

    @staticmethod
    def _to_entity(model: PaymentModel) -> Payment:
        """Convert ORM model to Payment entity."""
        return Payment(
            id=model.id,
            sale_id=model.sale_id,
            method=PaymentMethod(model.method),
            amount=Money(model.amount, model.currency),
            status=PaymentStatus(model.status),
            provider=PaymentProvider(model.provider),
            provider_transaction_id=model.provider_transaction_id,
            provider_metadata=model.provider_metadata or {},
            card_last4=model.card_last4,
            card_brand=model.card_brand,
            authorized_at=model.authorized_at,
            captured_at=model.captured_at,
            refunded_amount=Money(model.refunded_amount, model.currency),
            refunded_at=model.refunded_at,
            created_at=model.created_at,
            created_by=model.created_by,
            notes=model.notes,
            version=model.version,
        )
