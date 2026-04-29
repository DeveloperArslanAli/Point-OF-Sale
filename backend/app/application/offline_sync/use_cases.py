"""Offline sync use cases."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Sequence

import structlog

from app.application.offline_sync import IIdempotencyStore
from app.application.sales.use_cases.record_sale import (
    RecordSaleInput,
    RecordSaleUseCase,
    SaleLineInput,
    SalePaymentInput,
)
from app.application.shifts.use_cases import (
    EndShiftInput,
    EndShiftUseCase,
    StartShiftInput,
    StartShiftUseCase,
)
from app.application.cash_drawer.use_cases import (
    CloseDrawerInput,
    CloseCashDrawerUseCase,
    OpenDrawerInput,
    OpenCashDrawerUseCase,
    RecordMovementInput,
    RecordCashMovementUseCase,
)
from app.domain.offline_sync import (
    OfflineActionType,
    OfflineItemStatus,
    OfflineQueueItem,
    OfflineSyncBatch,
)

logger = structlog.get_logger()


@dataclass(slots=True)
class OfflineItemResult:
    """Result of processing a single offline item."""

    idempotency_key: str
    status: OfflineItemStatus
    error: str | None = None
    result_id: str | None = None


@dataclass(slots=True)
class ProcessOfflineSyncInput:
    """Input for processing offline sync batch."""

    terminal_id: str
    user_id: str
    items: list[dict[str, Any]]


@dataclass(slots=True)
class ProcessOfflineSyncResult:
    """Result of processing offline sync batch."""

    batch_id: str
    terminal_id: str
    total_items: int
    completed_count: int
    failed_count: int
    skipped_count: int
    success_rate: float
    started_at: datetime
    completed_at: datetime | None
    results: list[OfflineItemResult]


class ProcessOfflineSyncUseCase:
    """
    Use case for processing offline sync batches.

    Handles idempotency checking and dispatches each action
    to the appropriate handler.
    """

    def __init__(
        self,
        idempotency_store: IIdempotencyStore,
        record_sale_uc: RecordSaleUseCase | None = None,
        start_shift_uc: StartShiftUseCase | None = None,
        end_shift_uc: EndShiftUseCase | None = None,
        open_drawer_uc: OpenCashDrawerUseCase | None = None,
        close_drawer_uc: CloseCashDrawerUseCase | None = None,
        record_movement_uc: RecordCashMovementUseCase | None = None,
    ) -> None:
        self._idempotency_store = idempotency_store
        self._record_sale_uc = record_sale_uc
        self._start_shift_uc = start_shift_uc
        self._end_shift_uc = end_shift_uc
        self._open_drawer_uc = open_drawer_uc
        self._close_drawer_uc = close_drawer_uc
        self._record_movement_uc = record_movement_uc

    async def execute(self, data: ProcessOfflineSyncInput) -> ProcessOfflineSyncResult:
        """
        Process a batch of offline actions.

        Each action is processed with idempotency checking to prevent duplicates.
        """
        log = logger.bind(terminal_id=data.terminal_id, user_id=data.user_id)
        log.info("offline_sync_started", item_count=len(data.items))

        # Create queue items from input
        queue_items = []
        for item_data in data.items:
            queue_item = OfflineQueueItem.create(
                idempotency_key=item_data["idempotency_key"],
                action_type=item_data["action_type"],
                terminal_id=data.terminal_id,
                user_id=data.user_id,
                payload=item_data["payload"],
                created_offline_at=item_data.get("created_offline_at"),
            )
            queue_items.append(queue_item)

        # Create batch
        batch = OfflineSyncBatch.create(
            terminal_id=data.terminal_id,
            user_id=data.user_id,
            items=queue_items,
        )

        results: list[OfflineItemResult] = []

        # Process each item
        for item in queue_items:
            result = await self._process_item(item, data.user_id)
            results.append(result)
            batch.record_completion(item)

        batch.finalize()

        log.info(
            "offline_sync_completed",
            batch_id=batch.id,
            total=batch.total_items,
            completed=batch.completed_count,
            failed=batch.failed_count,
            skipped=batch.skipped_count,
            success_rate=batch.success_rate,
        )

        return ProcessOfflineSyncResult(
            batch_id=batch.id,
            terminal_id=batch.terminal_id,
            total_items=batch.total_items,
            completed_count=batch.completed_count,
            failed_count=batch.failed_count,
            skipped_count=batch.skipped_count,
            success_rate=batch.success_rate,
            started_at=batch.started_at,
            completed_at=batch.completed_at,
            results=results,
        )

    async def _process_item(
        self,
        item: OfflineQueueItem,
        user_id: str,
    ) -> OfflineItemResult:
        """Process a single offline queue item."""
        action_type_value = item.action_type.value if isinstance(item.action_type, OfflineActionType) else item.action_type
        log = logger.bind(
            idempotency_key=item.idempotency_key,
            action_type=action_type_value,
        )

        # Check idempotency
        if await self._idempotency_store.check_key(item.idempotency_key):
            result_id = await self._idempotency_store.get_result(item.idempotency_key)
            item.mark_skipped("Duplicate idempotency key")
            log.info("offline_item_skipped_duplicate", result_id=result_id)
            return OfflineItemResult(
                idempotency_key=item.idempotency_key,
                status=OfflineItemStatus.SKIPPED,
                error="Duplicate idempotency key",
                result_id=result_id,
            )

        item.mark_processing()

        try:
            result_id = await self._dispatch_action(item, user_id)
            item.mark_completed()

            # Store idempotency key
            await self._idempotency_store.store_key(item.idempotency_key, result_id)

            log.info("offline_item_completed", result_id=result_id)
            return OfflineItemResult(
                idempotency_key=item.idempotency_key,
                status=OfflineItemStatus.COMPLETED,
                result_id=result_id,
            )

        except Exception as e:
            error_msg = str(e)
            item.mark_failed(error_msg)
            log.warning("offline_item_failed", error=error_msg)
            return OfflineItemResult(
                idempotency_key=item.idempotency_key,
                status=OfflineItemStatus.FAILED,
                error=error_msg,
            )

    async def _dispatch_action(
        self,
        item: OfflineQueueItem,
        user_id: str,
    ) -> str | None:
        """Dispatch action to appropriate handler and return result ID."""
        payload = item.payload

        # Handle unknown action types (strings that couldn't be converted)
        if not isinstance(item.action_type, OfflineActionType):
            raise ValueError(f"Unsupported action type: {item.action_type}")

        if item.action_type == OfflineActionType.SALE:
            if not self._record_sale_uc:
                raise ValueError("Sale processing not configured")

            result = await self._record_sale_uc.execute(
                RecordSaleInput(
                    currency=payload.get("currency", "USD"),
                    customer_id=payload.get("customer_id"),
                    shift_id=payload.get("shift_id"),
                    lines=[
                        SaleLineInput(
                            product_id=line["product_id"],
                            quantity=line["quantity"],
                            unit_price=Decimal(str(line["unit_price"])),
                        )
                        for line in payload["lines"]
                    ],
                    payments=[
                        SalePaymentInput(
                            payment_method=p["payment_method"],
                            amount=Decimal(str(p["amount"])),
                            reference_number=p.get("reference_number"),
                            card_last_four=p.get("card_last_four"),
                            gift_card_code=p.get("gift_card_code"),
                        )
                        for p in payload["payments"]
                    ],
                )
            )
            return result.sale.id

        elif item.action_type == OfflineActionType.SHIFT_START:
            if not self._start_shift_uc:
                raise ValueError("Shift processing not configured")

            result = await self._start_shift_uc.execute(
                StartShiftInput(
                    user_id=user_id,
                    terminal_id=payload["terminal_id"],
                    drawer_session_id=payload.get("drawer_session_id"),
                    opening_cash=Decimal(str(payload["opening_cash"])) if payload.get("opening_cash") else None,
                    currency=payload.get("currency", "USD"),
                )
            )
            return result.id

        elif item.action_type == OfflineActionType.SHIFT_END:
            if not self._end_shift_uc:
                raise ValueError("Shift processing not configured")

            result = await self._end_shift_uc.execute(
                EndShiftInput(
                    shift_id=payload["shift_id"],
                    closing_cash=Decimal(str(payload["closing_cash"])) if payload.get("closing_cash") else None,
                )
            )
            return result.id

        elif item.action_type == OfflineActionType.DRAWER_OPEN:
            if not self._open_drawer_uc:
                raise ValueError("Drawer processing not configured")

            result = await self._open_drawer_uc.execute(
                OpenDrawerInput(
                    terminal_id=payload["terminal_id"],
                    user_id=user_id,
                    opening_float=Decimal(str(payload["opening_amount"])),
                    currency=payload.get("currency", "USD"),
                )
            )
            return result.id

        elif item.action_type == OfflineActionType.DRAWER_CLOSE:
            if not self._close_drawer_uc:
                raise ValueError("Drawer processing not configured")

            result = await self._close_drawer_uc.execute(
                CloseDrawerInput(
                    session_id=payload["session_id"],
                    user_id=user_id,
                    closing_count=Decimal(str(payload["closing_amount"])),
                )
            )
            return result.id

        elif item.action_type == OfflineActionType.DRAWER_MOVEMENT:
            if not self._record_movement_uc:
                raise ValueError("Drawer processing not configured")

            result = await self._record_movement_uc.execute(
                RecordMovementInput(
                    session_id=payload["session_id"],
                    movement_type=payload["movement_type"],
                    amount=Decimal(str(payload["amount"])),
                    reason=payload.get("notes"),
                )
            )
            return result.id

        else:
            raise ValueError(f"Unsupported action type: {item.action_type}")
