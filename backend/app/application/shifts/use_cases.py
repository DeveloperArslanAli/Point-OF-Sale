"""Shift use cases."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

import structlog

from app.application.cash_drawer import ICashDrawerRepository
from app.application.shifts import IShiftRepository
from app.domain.common.errors import NotFoundError, ValidationError
from app.domain.shifts import Shift

logger = structlog.get_logger()


@dataclass(slots=True)
class StartShiftInput:
    """Input for starting a shift."""

    user_id: str
    terminal_id: str
    drawer_session_id: str | None = None
    opening_cash: Decimal | None = None
    currency: str = "USD"


@dataclass(slots=True)
class EndShiftInput:
    """Input for ending a shift."""

    shift_id: str
    closing_cash: Decimal | None = None


@dataclass(slots=True)
class RecordSaleToShiftInput:
    """Input for recording a sale to a shift."""

    shift_id: str
    sale_total: Decimal
    cash_amount: Decimal = Decimal("0")
    card_amount: Decimal = Decimal("0")
    gift_card_amount: Decimal = Decimal("0")
    other_amount: Decimal = Decimal("0")


class StartShiftUseCase:
    """Use case for starting a shift."""

    def __init__(
        self,
        shift_repo: IShiftRepository,
        drawer_repo: ICashDrawerRepository | None = None,
    ) -> None:
        self._shift_repo = shift_repo
        self._drawer_repo = drawer_repo

    async def execute(self, data: StartShiftInput) -> Shift:
        """
        Start a new shift.

        Validates no active shift exists for the user.
        """
        log = logger.bind(user_id=data.user_id, terminal_id=data.terminal_id)

        # Check for existing active shift for user
        existing = await self._shift_repo.get_active_shift_for_user(data.user_id)
        if existing:
            log.warning("user_has_active_shift", shift_id=existing.id)
            raise ValidationError(
                f"User {data.user_id} already has an active shift",
                code="shift.already_active",
            )

        # Validate drawer session if provided
        if data.drawer_session_id and self._drawer_repo:
            drawer = await self._drawer_repo.get_by_id(data.drawer_session_id)
            if not drawer:
                raise NotFoundError(f"Drawer session {data.drawer_session_id} not found")
            if not drawer.is_open:
                raise ValidationError(
                    "Cannot link to a closed drawer session",
                    code="shift.drawer_closed",
                )

        shift = Shift.start(
            user_id=data.user_id,
            terminal_id=data.terminal_id,
            drawer_session_id=data.drawer_session_id,
            opening_cash=data.opening_cash,
            currency=data.currency,
        )

        await self._shift_repo.add(shift)
        log.info("shift_started", shift_id=shift.id)

        return shift


class EndShiftUseCase:
    """Use case for ending a shift."""

    def __init__(self, repository: IShiftRepository) -> None:
        self._repo = repository

    async def execute(self, data: EndShiftInput) -> Shift:
        """End a shift."""
        log = logger.bind(shift_id=data.shift_id)

        shift = await self._repo.get_by_id(data.shift_id)
        if not shift:
            raise NotFoundError(f"Shift {data.shift_id} not found")

        shift.end_shift(closing_cash=data.closing_cash)
        await self._repo.update(shift)

        log.info(
            "shift_ended",
            total_sales=str(shift.total_sales.amount),
            total_transactions=shift.total_transactions,
            duration_minutes=shift.duration_minutes,
        )

        return shift


class RecordSaleToShiftUseCase:
    """Use case for recording a sale to a shift."""

    def __init__(self, repository: IShiftRepository) -> None:
        self._repo = repository

    async def execute(self, data: RecordSaleToShiftInput) -> Shift:
        """Record a sale's payment breakdown to shift totals."""
        shift = await self._repo.get_by_id(data.shift_id)
        if not shift:
            raise NotFoundError(f"Shift {data.shift_id} not found")

        shift.record_sale(
            sale_total=data.sale_total,
            cash_amount=data.cash_amount,
            card_amount=data.card_amount,
            gift_card_amount=data.gift_card_amount,
            other_amount=data.other_amount,
        )

        await self._repo.update(shift)
        return shift


class GetShiftUseCase:
    """Use case for retrieving a shift."""

    def __init__(self, repository: IShiftRepository) -> None:
        self._repo = repository

    async def execute(self, shift_id: str) -> Shift:
        """Get a shift by ID."""
        shift = await self._repo.get_by_id(shift_id)
        if not shift:
            raise NotFoundError(f"Shift {shift_id} not found")
        return shift


class GetActiveShiftForUserUseCase:
    """Use case for getting the active shift for a user."""

    def __init__(self, repository: IShiftRepository) -> None:
        self._repo = repository

    async def execute(self, user_id: str) -> Shift | None:
        """Get the currently active shift for a user."""
        return await self._repo.get_active_shift_for_user(user_id)


@dataclass(slots=True)
class ListShiftsInput:
    """Input for listing shifts."""

    user_id: str | None = None
    terminal_id: str | None = None
    status: str | None = None
    page: int = 1
    limit: int = 20


@dataclass(slots=True)
class ListShiftsResult:
    """Result for listing shifts."""

    shifts: Sequence[Shift]
    total: int
    page: int
    limit: int
    pages: int


class ListShiftsUseCase:
    """Use case for listing shifts."""

    def __init__(self, repository: IShiftRepository) -> None:
        self._repo = repository

    async def execute(self, data: ListShiftsInput) -> ListShiftsResult:
        """List shifts with pagination."""
        offset = (data.page - 1) * data.limit
        shifts, total = await self._repo.list_shifts(
            user_id=data.user_id,
            terminal_id=data.terminal_id,
            status=data.status,
            offset=offset,
            limit=data.limit,
        )

        pages = (total + data.limit - 1) // data.limit if total > 0 else 1

        return ListShiftsResult(
            shifts=shifts,
            total=total,
            page=data.page,
            limit=data.limit,
            pages=pages,
        )
