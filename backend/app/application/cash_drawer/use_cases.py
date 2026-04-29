"""Cash drawer use cases."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

import structlog

from app.application.cash_drawer import ICashDrawerRepository
from app.domain.cash_drawer import CashDrawerSession, CashMovement, DrawerStatus, MovementType
from app.domain.common.errors import NotFoundError, ValidationError

logger = structlog.get_logger()


@dataclass(slots=True)
class OpenDrawerInput:
    """Input for opening a cash drawer."""

    terminal_id: str
    user_id: str
    opening_float: Decimal
    currency: str = "USD"


@dataclass(slots=True)
class CloseDrawerInput:
    """Input for closing a cash drawer."""

    session_id: str
    user_id: str
    closing_count: Decimal


@dataclass(slots=True)
class RecordMovementInput:
    """Input for recording a cash movement."""

    session_id: str
    movement_type: str
    amount: Decimal
    reason: str | None = None
    reference_id: str | None = None


class OpenCashDrawerUseCase:
    """Use case for opening a cash drawer session."""

    def __init__(self, repository: ICashDrawerRepository) -> None:
        self._repo = repository

    async def execute(self, data: OpenDrawerInput) -> CashDrawerSession:
        """
        Open a new cash drawer session.

        Validates no other session is open for the terminal.
        """
        log = logger.bind(terminal_id=data.terminal_id, user_id=data.user_id)

        # Check for existing open session
        existing = await self._repo.get_open_session_for_terminal(data.terminal_id)
        if existing:
            log.warning("drawer_already_open", session_id=existing.id)
            raise ValidationError(
                f"Terminal {data.terminal_id} already has an open drawer session",
                code="cash_drawer.already_open",
            )

        session = CashDrawerSession.open_drawer(
            terminal_id=data.terminal_id,
            opened_by=data.user_id,
            opening_float=data.opening_float,
            currency=data.currency,
        )

        await self._repo.add(session)
        log.info("drawer_opened", session_id=session.id, opening_float=str(data.opening_float))

        return session


class CloseCashDrawerUseCase:
    """Use case for closing a cash drawer session."""

    def __init__(self, repository: ICashDrawerRepository) -> None:
        self._repo = repository

    async def execute(self, data: CloseDrawerInput) -> CashDrawerSession:
        """
        Close a cash drawer session with counted cash.

        Calculates over/short based on expected vs counted.
        """
        log = logger.bind(session_id=data.session_id, user_id=data.user_id)

        session = await self._repo.get_by_id(data.session_id)
        if not session:
            raise NotFoundError(f"Cash drawer session {data.session_id} not found")

        session.close_drawer(closed_by=data.user_id, closing_count=data.closing_count)

        await self._repo.update(session)

        over_short = session.over_short.amount if session.over_short else Decimal("0")
        log.info(
            "drawer_closed",
            closing_count=str(data.closing_count),
            expected=str(session.expected_balance.amount),
            over_short=str(over_short),
        )

        return session


class RecordCashMovementUseCase:
    """Use case for recording a cash movement."""

    def __init__(self, repository: ICashDrawerRepository) -> None:
        self._repo = repository

    async def execute(self, data: RecordMovementInput) -> CashMovement:
        """
        Record a cash movement (pay-in, payout, sale, change, refund).
        """
        log = logger.bind(session_id=data.session_id, movement_type=data.movement_type)

        session = await self._repo.get_by_id(data.session_id)
        if not session:
            raise NotFoundError(f"Cash drawer session {data.session_id} not found")

        try:
            movement_type = MovementType(data.movement_type)
        except ValueError as exc:
            raise ValidationError(
                f"Invalid movement type: {data.movement_type}",
                code="cash_movement.invalid_type",
            ) from exc

        movement = session.record_movement(
            movement_type=movement_type,
            amount=data.amount,
            reason=data.reason,
            reference_id=data.reference_id,
        )

        await self._repo.add_movement(movement)
        await self._repo.update(session)

        log.info(
            "movement_recorded",
            movement_id=movement.id,
            amount=str(data.amount),
            new_balance=str(session.expected_balance.amount),
        )

        return movement


class GetCashDrawerSessionUseCase:
    """Use case for retrieving a cash drawer session."""

    def __init__(self, repository: ICashDrawerRepository) -> None:
        self._repo = repository

    async def execute(self, session_id: str) -> CashDrawerSession:
        """Get a cash drawer session by ID."""
        session = await self._repo.get_by_id(session_id)
        if not session:
            raise NotFoundError(f"Cash drawer session {session_id} not found")
        return session


class GetOpenDrawerForTerminalUseCase:
    """Use case for getting the open drawer for a terminal."""

    def __init__(self, repository: ICashDrawerRepository) -> None:
        self._repo = repository

    async def execute(self, terminal_id: str) -> CashDrawerSession | None:
        """Get the currently open drawer session for a terminal."""
        return await self._repo.get_open_session_for_terminal(terminal_id)


@dataclass(slots=True)
class ListDrawerSessionsInput:
    """Input for listing drawer sessions."""

    terminal_id: str | None = None
    status: str | None = None
    page: int = 1
    limit: int = 20


@dataclass(slots=True)
class ListDrawerSessionsResult:
    """Result for listing drawer sessions."""

    sessions: Sequence[CashDrawerSession]
    total: int
    page: int
    limit: int
    pages: int


class ListCashDrawerSessionsUseCase:
    """Use case for listing cash drawer sessions."""

    def __init__(self, repository: ICashDrawerRepository) -> None:
        self._repo = repository

    async def execute(self, data: ListDrawerSessionsInput) -> ListDrawerSessionsResult:
        """List cash drawer sessions with pagination."""
        offset = (data.page - 1) * data.limit
        sessions, total = await self._repo.list_sessions(
            terminal_id=data.terminal_id,
            status=data.status,
            offset=offset,
            limit=data.limit,
        )

        pages = (total + data.limit - 1) // data.limit if total > 0 else 1

        return ListDrawerSessionsResult(
            sessions=sessions,
            total=total,
            page=data.page,
            limit=data.limit,
            pages=pages,
        )
