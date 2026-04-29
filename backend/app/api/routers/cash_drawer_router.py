"""Cash drawer API router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_roles, SALES_ROLES
from app.api.schemas.cash_drawer import (
    CashDrawerSessionOut,
    CashMovementOut,
    CloseDrawerRequest,
    DrawerSessionListOut,
    DrawerTotalsOut,
    OpenDrawerRequest,
    RecordMovementRequest,
)
from app.application.cash_drawer.use_cases import (
    CloseCashDrawerUseCase,
    CloseDrawerInput,
    GetCashDrawerSessionUseCase,
    GetOpenDrawerForTerminalUseCase,
    ListCashDrawerSessionsUseCase,
    ListDrawerSessionsInput,
    OpenCashDrawerUseCase,
    OpenDrawerInput,
    RecordCashMovementUseCase,
    RecordMovementInput,
)
from app.domain.auth.entities import User, UserRole
from app.domain.cash_drawer import CashDrawerSession
from app.infrastructure.db.repositories.cash_drawer_repository import SqlAlchemyCashDrawerRepository
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/cash-drawer", tags=["cash-drawer"])


def _session_to_out(session: CashDrawerSession) -> CashDrawerSessionOut:
    """Convert domain session to response schema."""
    totals = session.calculate_totals()
    net_cash = totals["sales"] - totals["change"] - totals["refunds"]

    return CashDrawerSessionOut(
        id=session.id,
        terminal_id=session.terminal_id,
        opened_by=session.opened_by,
        closed_by=session.closed_by,
        opening_amount=session.opening_float.amount,
        closing_amount=session.closing_count.amount if session.closing_count else None,
        expected_balance=session.expected_balance.amount,
        over_short=session.over_short.amount if session.over_short else None,
        currency=session.opening_float.currency,
        status=session.status.value,
        opened_at=session.opened_at,
        closed_at=session.closed_at,
        version=session.version,
        movements=[
            CashMovementOut(
                id=m.id,
                drawer_session_id=m.drawer_session_id,
                movement_type=m.movement_type.value,
                amount=m.amount.amount,
                currency=m.amount.currency,
                reason=m.reason,
                reference_id=m.reference_id,
                created_at=m.created_at,
            )
            for m in session.movements
        ],
        totals=DrawerTotalsOut(
            pay_in=totals["pay_in"],
            payout=totals["payout"],
            sales=totals["sales"],
            change=totals["change"],
            refunds=totals["refunds"],
            net_cash_sales=net_cash,
        ),
    )


@router.post("/open", response_model=CashDrawerSessionOut, status_code=status.HTTP_201_CREATED)
async def open_drawer(
    payload: OpenDrawerRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*SALES_ROLES)),
) -> CashDrawerSessionOut:
    """
    Open a new cash drawer session.

    Creates a new session with the specified opening float.
    Only one session can be open per terminal.

    Requires: SALES_ROLES (cashier, manager, admin)
    """
    repo = SqlAlchemyCashDrawerRepository(session)
    use_case = OpenCashDrawerUseCase(repo)

    drawer = await use_case.execute(
        OpenDrawerInput(
            terminal_id=payload.terminal_id,
            user_id=current_user.id,
            opening_float=payload.opening_amount,
            currency=payload.currency,
        )
    )

    return _session_to_out(drawer)


@router.post("/close", response_model=CashDrawerSessionOut)
async def close_drawer(
    payload: CloseDrawerRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*SALES_ROLES)),
) -> CashDrawerSessionOut:
    """
    Close a cash drawer session.

    Calculates over/short based on expected balance vs counted amount.

    Requires: SALES_ROLES (cashier, manager, admin)
    """
    repo = SqlAlchemyCashDrawerRepository(session)
    use_case = CloseCashDrawerUseCase(repo)

    drawer = await use_case.execute(
        CloseDrawerInput(
            session_id=payload.session_id,
            user_id=current_user.id,
            closing_count=payload.closing_amount,
        )
    )

    return _session_to_out(drawer)


@router.post("/movements", response_model=CashMovementOut, status_code=status.HTTP_201_CREATED)
async def record_movement(
    payload: RecordMovementRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*SALES_ROLES)),
) -> CashMovementOut:
    """
    Record a cash movement (drop, pickup, pay-in, payout).

    Updates the expected balance accordingly.

    Requires: SALES_ROLES (cashier, manager, admin)
    """
    repo = SqlAlchemyCashDrawerRepository(session)
    use_case = RecordCashMovementUseCase(repo)

    movement = await use_case.execute(
        RecordMovementInput(
            session_id=payload.session_id,
            movement_type=payload.movement_type,
            amount=payload.amount,
            reason=payload.notes,
            reference_id=None,
        )
    )

    return CashMovementOut(
        id=movement.id,
        drawer_session_id=movement.drawer_session_id,
        movement_type=movement.movement_type.value,
        amount=movement.amount.amount,
        currency=movement.amount.currency,
        reason=movement.reason,
        reference_id=movement.reference_id,
        created_at=movement.created_at,
    )


@router.get("/{session_id}", response_model=CashDrawerSessionOut)
async def get_drawer_session(
    session_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*SALES_ROLES)),
) -> CashDrawerSessionOut:
    """
    Get a cash drawer session by ID.

    Requires: SALES_ROLES (cashier, manager, admin)
    """
    repo = SqlAlchemyCashDrawerRepository(session)
    use_case = GetCashDrawerSessionUseCase(repo)
    drawer = await use_case.execute(session_id)
    return _session_to_out(drawer)


@router.get("/terminal/{terminal_id}/open", response_model=CashDrawerSessionOut)
async def get_open_drawer_for_terminal(
    terminal_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*SALES_ROLES)),
) -> CashDrawerSessionOut:
    """
    Get the currently open drawer session for a terminal.

    Returns 404 if no session is open.

    Requires: SALES_ROLES (cashier, manager, admin)
    """
    repo = SqlAlchemyCashDrawerRepository(session)
    use_case = GetOpenDrawerForTerminalUseCase(repo)
    drawer = await use_case.execute(terminal_id)
    if not drawer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No open drawer for terminal"
        )
    return _session_to_out(drawer)


@router.get("", response_model=DrawerSessionListOut)
async def list_drawer_sessions(
    terminal_id: str | None = Query(None, description="Filter by terminal"),
    status: str | None = Query(None, description="Filter by status (open/closed)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPER_ADMIN)),
) -> DrawerSessionListOut:
    """
    List cash drawer sessions with pagination.

    Requires: Manager or higher roles
    """
    repo = SqlAlchemyCashDrawerRepository(session)
    use_case = ListCashDrawerSessionsUseCase(repo)

    result = await use_case.execute(
        ListDrawerSessionsInput(
            terminal_id=terminal_id,
            status=status,
            page=page,
            limit=limit,
        )
    )

    return DrawerSessionListOut(
        items=[_session_to_out(s) for s in result.sessions],
        total=result.total,
        page=result.page,
        limit=result.limit,
        pages=result.pages,
    )
