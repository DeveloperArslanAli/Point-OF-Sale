"""Shift repository implementation."""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shifts import IShiftRepository
from app.core.tenant import get_current_tenant_id
from app.domain.common.money import Money
from app.domain.shifts import Shift, ShiftStatus
from app.infrastructure.db.models.shift_model import ShiftModel


class SqlAlchemyShiftRepository(IShiftRepository):
    """SQLAlchemy implementation of shift repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id and hasattr(ShiftModel, "tenant_id"):
            return stmt.where(ShiftModel.tenant_id == tenant_id)
        return stmt

    async def add(self, shift: Shift) -> None:
        """Add a new shift."""
        model = self._entity_to_model(shift)
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, shift_id: str) -> Shift | None:
        """Get a shift by ID."""
        stmt = select(ShiftModel).where(ShiftModel.id == shift_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model else None

    async def get_active_shift_for_user(self, user_id: str) -> Shift | None:
        """Get the currently active shift for a user."""
        stmt = select(ShiftModel).where(
            ShiftModel.user_id == user_id,
            ShiftModel.status == ShiftStatus.ACTIVE.value,
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model else None

    async def get_active_shift_for_terminal(self, terminal_id: str) -> Shift | None:
        """Get the currently active shift for a terminal."""
        stmt = select(ShiftModel).where(
            ShiftModel.terminal_id == terminal_id,
            ShiftModel.status == ShiftStatus.ACTIVE.value,
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model else None

    async def update(self, shift: Shift) -> None:
        """Update a shift."""
        stmt = select(ShiftModel).where(ShiftModel.id == shift.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            msg = f"Shift {shift.id} not found"
            raise ValueError(msg)

        # Update fields
        model.drawer_session_id = shift.drawer_session_id
        model.status = shift.status.value
        model.ended_at = shift.ended_at
        model.opening_cash = shift.opening_cash.amount if shift.opening_cash else None
        model.closing_cash = shift.closing_cash.amount if shift.closing_cash else None
        model.total_sales = shift.total_sales.amount
        model.total_transactions = shift.total_transactions
        model.cash_sales = shift.cash_sales.amount
        model.card_sales = shift.card_sales.amount
        model.gift_card_sales = shift.gift_card_sales.amount
        model.other_sales = shift.other_sales.amount
        model.total_refunds = shift.total_refunds.amount
        model.refund_count = shift.refund_count
        model.version = shift.version

        await self._session.flush()

    async def list_shifts(
        self,
        *,
        user_id: str | None = None,
        terminal_id: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Shift], int]:
        """List shifts with optional filters."""
        stmt = select(ShiftModel).order_by(ShiftModel.started_at.desc())
        count_stmt = select(func.count(ShiftModel.id))

        # Apply tenant filter
        stmt = self._apply_tenant_filter(stmt)
        count_stmt = self._apply_tenant_filter(count_stmt)

        if user_id:
            stmt = stmt.where(ShiftModel.user_id == user_id)
            count_stmt = count_stmt.where(ShiftModel.user_id == user_id)
        if terminal_id:
            stmt = stmt.where(ShiftModel.terminal_id == terminal_id)
            count_stmt = count_stmt.where(ShiftModel.terminal_id == terminal_id)
        if status:
            stmt = stmt.where(ShiftModel.status == status)
            count_stmt = count_stmt.where(ShiftModel.status == status)

        stmt = stmt.offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        shifts = [self._model_to_entity(m) for m in models]
        return shifts, int(total)

    def _entity_to_model(self, entity: Shift) -> ShiftModel:
        """Convert domain entity to ORM model."""
        tenant_id = get_current_tenant_id()
        return ShiftModel(
            id=entity.id,
            user_id=entity.user_id,
            terminal_id=entity.terminal_id,
            drawer_session_id=entity.drawer_session_id,
            status=entity.status.value,
            started_at=entity.started_at,
            ended_at=entity.ended_at,
            opening_cash=entity.opening_cash.amount if entity.opening_cash else None,
            closing_cash=entity.closing_cash.amount if entity.closing_cash else None,
            total_sales=entity.total_sales.amount,
            total_transactions=entity.total_transactions,
            cash_sales=entity.cash_sales.amount,
            card_sales=entity.card_sales.amount,
            gift_card_sales=entity.gift_card_sales.amount,
            other_sales=entity.other_sales.amount,
            total_refunds=entity.total_refunds.amount,
            refund_count=entity.refund_count,
            currency=entity.total_sales.currency,
            version=entity.version,
            tenant_id=tenant_id,
        )

    def _model_to_entity(self, model: ShiftModel) -> Shift:
        """Convert ORM model to domain entity."""
        currency = model.currency
        return Shift(
            id=model.id,
            user_id=model.user_id,
            terminal_id=model.terminal_id,
            drawer_session_id=model.drawer_session_id,
            status=ShiftStatus(model.status),
            started_at=model.started_at,
            ended_at=model.ended_at,
            opening_cash=Money(Decimal(str(model.opening_cash)), currency) if model.opening_cash is not None else None,
            closing_cash=Money(Decimal(str(model.closing_cash)), currency) if model.closing_cash is not None else None,
            total_sales=Money(Decimal(str(model.total_sales)), currency),
            total_transactions=model.total_transactions,
            cash_sales=Money(Decimal(str(model.cash_sales)), currency),
            card_sales=Money(Decimal(str(model.card_sales)), currency),
            gift_card_sales=Money(Decimal(str(model.gift_card_sales)), currency),
            other_sales=Money(Decimal(str(model.other_sales)), currency),
            total_refunds=Money(Decimal(str(model.total_refunds)), currency),
            refund_count=model.refund_count,
            version=model.version,
        )
