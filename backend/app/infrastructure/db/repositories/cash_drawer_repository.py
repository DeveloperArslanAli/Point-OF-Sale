"""Cash drawer repository implementation."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.cash_drawer import ICashDrawerRepository
from app.core.tenant import get_current_tenant_id
from app.domain.cash_drawer import CashDrawerSession, CashMovement, DrawerStatus, MovementType
from app.domain.common.money import Money
from app.infrastructure.db.models.cash_drawer_model import (
    CashDrawerSessionModel,
    CashMovementModel,
)


class SqlAlchemyCashDrawerRepository(ICashDrawerRepository):
    """SQLAlchemy implementation of cash drawer repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt: Select[Any]) -> Select[Any]:
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(CashDrawerSessionModel.tenant_id == tenant_id)
        return stmt

    async def add(self, drawer_session: CashDrawerSession) -> None:
        """Add a new cash drawer session."""
        model = self._session_to_model(drawer_session)
        model.tenant_id = get_current_tenant_id()
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, session_id: str) -> CashDrawerSession | None:
        """Get a cash drawer session by ID."""
        stmt = (
            select(CashDrawerSessionModel)
            .options(selectinload(CashDrawerSessionModel.movements))
            .where(CashDrawerSessionModel.id == session_id)
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_session(model) if model else None

    async def get_open_session_for_terminal(self, terminal_id: str) -> CashDrawerSession | None:
        """Get the currently open session for a terminal."""
        stmt = (
            select(CashDrawerSessionModel)
            .options(selectinload(CashDrawerSessionModel.movements))
            .where(
                CashDrawerSessionModel.terminal_id == terminal_id,
                CashDrawerSessionModel.status == DrawerStatus.OPEN.value,
            )
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_session(model) if model else None

    async def update(self, drawer_session: CashDrawerSession) -> None:
        """Update a cash drawer session."""
        stmt = select(CashDrawerSessionModel).where(
            CashDrawerSessionModel.id == drawer_session.id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            msg = f"Cash drawer session {drawer_session.id} not found"
            raise ValueError(msg)

        # Update fields
        model.closed_by = drawer_session.closed_by
        model.closing_count = drawer_session.closing_count.amount if drawer_session.closing_count else None
        model.expected_balance = drawer_session.expected_balance.amount
        model.over_short = drawer_session.over_short.amount if drawer_session.over_short else None
        model.status = drawer_session.status.value
        model.closed_at = drawer_session.closed_at
        model.version = drawer_session.version

        await self._session.flush()

    async def add_movement(self, movement: CashMovement) -> None:
        """Add a cash movement to a session."""
        model = CashMovementModel(
            id=movement.id,
            drawer_session_id=movement.drawer_session_id,
            movement_type=movement.movement_type.value,
            amount=movement.amount.amount,
            currency=movement.amount.currency,
            reason=movement.reason,
            reference_id=movement.reference_id,
            created_at=movement.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_movements(self, session_id: str) -> Sequence[CashMovement]:
        """Get all movements for a session."""
        stmt = (
            select(CashMovementModel)
            .where(CashMovementModel.drawer_session_id == session_id)
            .order_by(CashMovementModel.created_at)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._movement_model_to_entity(m) for m in models]

    async def list_sessions(
        self,
        *,
        terminal_id: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[CashDrawerSession], int]:
        """List cash drawer sessions with optional filters."""
        stmt = (
            select(CashDrawerSessionModel)
            .options(selectinload(CashDrawerSessionModel.movements))
            .order_by(CashDrawerSessionModel.opened_at.desc())
        )
        count_stmt = select(func.count(CashDrawerSessionModel.id))
        
        # Apply tenant filter
        stmt = self._apply_tenant_filter(stmt)
        tenant_id = get_current_tenant_id()
        if tenant_id:
            count_stmt = count_stmt.where(CashDrawerSessionModel.tenant_id == tenant_id)

        if terminal_id:
            stmt = stmt.where(CashDrawerSessionModel.terminal_id == terminal_id)
            count_stmt = count_stmt.where(CashDrawerSessionModel.terminal_id == terminal_id)
        if status:
            stmt = stmt.where(CashDrawerSessionModel.status == status)
            count_stmt = count_stmt.where(CashDrawerSessionModel.status == status)

        stmt = stmt.offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        sessions = [self._model_to_session(m) for m in models]
        return sessions, int(total)

    def _session_to_model(self, entity: CashDrawerSession) -> CashDrawerSessionModel:
        """Convert domain entity to ORM model."""
        return CashDrawerSessionModel(
            id=entity.id,
            terminal_id=entity.terminal_id,
            opened_by=entity.opened_by,
            closed_by=entity.closed_by,
            opening_float=entity.opening_float.amount,
            closing_count=entity.closing_count.amount if entity.closing_count else None,
            expected_balance=entity.expected_balance.amount,
            over_short=entity.over_short.amount if entity.over_short else None,
            currency=entity.opening_float.currency,
            status=entity.status.value,
            opened_at=entity.opened_at,
            closed_at=entity.closed_at,
            version=entity.version,
        )

    def _model_to_session(self, model: CashDrawerSessionModel) -> CashDrawerSession:
        """Convert ORM model to domain entity."""
        currency = model.currency
        movements = [self._movement_model_to_entity(m) for m in model.movements]

        return CashDrawerSession(
            id=model.id,
            terminal_id=model.terminal_id,
            opened_by=model.opened_by,
            closed_by=model.closed_by,
            opening_float=Money(Decimal(str(model.opening_float)), currency),
            closing_count=Money(Decimal(str(model.closing_count)), currency) if model.closing_count is not None else None,
            expected_balance=Money(Decimal(str(model.expected_balance)), currency),
            over_short=Money(Decimal(str(model.over_short)), currency) if model.over_short is not None else None,
            status=DrawerStatus(model.status),
            opened_at=model.opened_at,
            closed_at=model.closed_at,
            version=model.version,
            movements=movements,
        )

    def _movement_model_to_entity(self, model: CashMovementModel) -> CashMovement:
        """Convert movement ORM model to domain entity."""
        return CashMovement(
            id=model.id,
            drawer_session_id=model.drawer_session_id,
            movement_type=MovementType(model.movement_type),
            amount=Money(Decimal(str(model.amount)), model.currency),
            reason=model.reason,
            reference_id=model.reference_id,
            created_at=model.created_at,
        )
