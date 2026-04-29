"""Shift API router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_roles, SALES_ROLES
from app.api.schemas.shift import EndShiftRequest, ShiftListOut, ShiftOut, StartShiftRequest
from app.application.shifts.use_cases import (
    EndShiftInput,
    EndShiftUseCase,
    GetActiveShiftForUserUseCase,
    GetShiftUseCase,
    ListShiftsInput,
    ListShiftsUseCase,
    StartShiftInput,
    StartShiftUseCase,
)
from app.domain.auth.entities import User, UserRole
from app.domain.shifts import Shift
from app.infrastructure.db.repositories.cash_drawer_repository import SqlAlchemyCashDrawerRepository
from app.infrastructure.db.repositories.shift_repository import SqlAlchemyShiftRepository
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/shifts", tags=["shifts"])


def _shift_to_out(shift: Shift) -> ShiftOut:
    """Convert domain shift to response schema."""
    return ShiftOut(
        id=shift.id,
        user_id=shift.user_id,
        terminal_id=shift.terminal_id,
        drawer_session_id=shift.drawer_session_id,
        status=shift.status.value,
        started_at=shift.started_at,
        ended_at=shift.ended_at,
        opening_cash=shift.opening_cash.amount if shift.opening_cash else None,
        closing_cash=shift.closing_cash.amount if shift.closing_cash else None,
        total_sales=shift.total_sales.amount,
        total_transactions=shift.total_transactions,
        cash_sales=shift.cash_sales.amount,
        card_sales=shift.card_sales.amount,
        gift_card_sales=shift.gift_card_sales.amount,
        other_sales=shift.other_sales.amount,
        total_refunds=shift.total_refunds.amount,
        refund_count=shift.refund_count,
        net_sales=shift.net_sales.amount,
        duration_minutes=shift.duration_minutes,
        currency=shift.total_sales.currency,
        version=shift.version,
    )


@router.post("/start", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
async def start_shift(
    payload: StartShiftRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*SALES_ROLES)),
) -> ShiftOut:
    """
    Start a new shift.

    Creates a new shift for the current user. Only one active shift per user.

    Requires: SALES_ROLES (cashier, manager, admin)
    """
    shift_repo = SqlAlchemyShiftRepository(session)
    drawer_repo = SqlAlchemyCashDrawerRepository(session)
    use_case = StartShiftUseCase(shift_repo, drawer_repo)

    shift = await use_case.execute(
        StartShiftInput(
            user_id=current_user.id,
            terminal_id=payload.terminal_id,
            drawer_session_id=payload.drawer_session_id,
            opening_cash=payload.opening_cash,
            currency=payload.currency,
        )
    )

    return _shift_to_out(shift)


@router.post("/end", response_model=ShiftOut)
async def end_shift(
    payload: EndShiftRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*SALES_ROLES)),
) -> ShiftOut:
    """
    End a shift.

    Closes the shift and calculates final totals.

    Requires: SALES_ROLES (cashier, manager, admin)
    """
    repo = SqlAlchemyShiftRepository(session)
    use_case = EndShiftUseCase(repo)

    shift = await use_case.execute(EndShiftInput(
        shift_id=payload.shift_id,
        closing_cash=payload.closing_cash,
    ))

    return _shift_to_out(shift)


@router.get("/active", response_model=ShiftOut)
async def get_active_shift(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*SALES_ROLES)),
) -> ShiftOut:
    """
    Get the active shift for the current user.

    Returns 404 if no active shift.

    Requires: SALES_ROLES (cashier, manager, admin)
    """
    repo = SqlAlchemyShiftRepository(session)
    use_case = GetActiveShiftForUserUseCase(repo)
    shift = await use_case.execute(current_user.id)
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active shift")
    return _shift_to_out(shift)


@router.get("/{shift_id}", response_model=ShiftOut)
async def get_shift(
    shift_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*SALES_ROLES)),
) -> ShiftOut:
    """
    Get a shift by ID.

    Requires: SALES_ROLES (cashier, manager, admin)
    """
    repo = SqlAlchemyShiftRepository(session)
    use_case = GetShiftUseCase(repo)
    shift = await use_case.execute(shift_id)
    return _shift_to_out(shift)


@router.get("", response_model=ShiftListOut)
async def list_shifts(
    user_id: str | None = Query(None, description="Filter by user"),
    terminal_id: str | None = Query(None, description="Filter by terminal"),
    status: str | None = Query(None, description="Filter by status (active/closed)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPER_ADMIN)),
) -> ShiftListOut:
    """
    List shifts with pagination.

    Requires: Manager or higher roles
    """
    repo = SqlAlchemyShiftRepository(session)
    use_case = ListShiftsUseCase(repo)

    result = await use_case.execute(
        ListShiftsInput(
            user_id=user_id,
            terminal_id=terminal_id,
            status=status,
            page=page,
            limit=limit,
        )
    )

    return ShiftListOut(
        items=[_shift_to_out(s) for s in result.shifts],
        total=result.total,
        page=result.page,
        limit=result.limit,
        pages=result.pages,
    )
