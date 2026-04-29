"""Offline sync API router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_roles, SALES_ROLES
from app.api.schemas.offline_sync import (
    OfflineItemResultOut,
    OfflineSyncRequest,
    OfflineSyncResultOut,
)
from app.application.offline_sync.use_cases import (
    ProcessOfflineSyncInput,
    ProcessOfflineSyncUseCase,
)
from app.application.sales.use_cases.record_sale import RecordSaleUseCase
from app.application.shifts.use_cases import (
    EndShiftUseCase,
    StartShiftUseCase,
)
from app.application.cash_drawer.use_cases import (
    CloseCashDrawerUseCase,
    OpenCashDrawerUseCase,
    RecordCashMovementUseCase,
)
from app.domain.auth.entities import User
from app.infrastructure.db.repositories.cash_drawer_repository import SqlAlchemyCashDrawerRepository
from app.infrastructure.db.repositories.customer_repository import SqlAlchemyCustomerRepository
from app.infrastructure.db.repositories.gift_card_repository import SqlAlchemyGiftCardRepository
from app.infrastructure.db.repositories.idempotency_store import SqlAlchemyIdempotencyStore
from app.infrastructure.db.repositories.inventory_movement_repository import SqlAlchemyInventoryMovementRepository
from app.infrastructure.db.repositories.inventory_repository import SqlAlchemyProductRepository
from app.infrastructure.db.repositories.sales_repository import SqlAlchemySalesRepository
from app.infrastructure.db.repositories.shift_repository import SqlAlchemyShiftRepository
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/replay", response_model=OfflineSyncResultOut, status_code=status.HTTP_200_OK)
async def replay_offline_actions(
    payload: OfflineSyncRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*SALES_ROLES)),
) -> OfflineSyncResultOut:
    """
    Replay offline actions that were queued while the terminal was disconnected.

    Each action includes an idempotency_key to prevent duplicate processing.
    Actions are processed in order. Failed actions are reported but don't
    stop processing of subsequent items.

    Supported action types:
    - sale: Record a sale
    - shift_start: Start a cashier shift
    - shift_end: End a cashier shift
    - drawer_open: Open a cash drawer
    - drawer_close: Close a cash drawer
    - drawer_movement: Record a cash movement

    Requires: SALES_ROLES (cashier, manager, admin)
    """
    # Initialize repositories
    idempotency_store = SqlAlchemyIdempotencyStore(session)
    product_repo = SqlAlchemyProductRepository(session)
    sales_repo = SqlAlchemySalesRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    customer_repo = SqlAlchemyCustomerRepository(session)
    gift_card_repo = SqlAlchemyGiftCardRepository(session)
    shift_repo = SqlAlchemyShiftRepository(session)
    drawer_repo = SqlAlchemyCashDrawerRepository(session)

    # Initialize use cases
    record_sale_uc = RecordSaleUseCase(
        product_repo,
        sales_repo,
        inventory_repo,
        customer_repo,
        gift_card_repo,
        shift_repo=shift_repo,
        drawer_repo=drawer_repo,
    )
    start_shift_uc = StartShiftUseCase(shift_repo, drawer_repo)
    end_shift_uc = EndShiftUseCase(shift_repo)
    open_drawer_uc = OpenCashDrawerUseCase(drawer_repo)
    close_drawer_uc = CloseCashDrawerUseCase(drawer_repo)
    record_movement_uc = RecordCashMovementUseCase(drawer_repo)

    # Create sync use case
    use_case = ProcessOfflineSyncUseCase(
        idempotency_store=idempotency_store,
        record_sale_uc=record_sale_uc,
        start_shift_uc=start_shift_uc,
        end_shift_uc=end_shift_uc,
        open_drawer_uc=open_drawer_uc,
        close_drawer_uc=close_drawer_uc,
        record_movement_uc=record_movement_uc,
    )

    # Prepare input
    items = [
        {
            "idempotency_key": item.idempotency_key,
            "action_type": item.action_type,
            "payload": item.payload,
            "created_offline_at": item.created_offline_at,
        }
        for item in payload.items
    ]

    # Execute
    result = await use_case.execute(
        ProcessOfflineSyncInput(
            terminal_id=payload.terminal_id,
            user_id=current_user.id,
            items=items,
        )
    )

    # Build response
    return OfflineSyncResultOut(
        batch_id=result.batch_id,
        terminal_id=result.terminal_id,
        total_items=result.total_items,
        completed_count=result.completed_count,
        failed_count=result.failed_count,
        skipped_count=result.skipped_count,
        success_rate=result.success_rate,
        started_at=result.started_at,
        completed_at=result.completed_at,
        results=[
            OfflineItemResultOut(
                idempotency_key=r.idempotency_key,
                status=r.status.value,
                error=r.error,
                result_id=r.result_id,
            )
            for r in result.results
        ],
    )
