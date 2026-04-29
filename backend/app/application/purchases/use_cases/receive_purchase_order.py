"""Use case for receiving purchase orders with exception handling.

Supports:
- Partial deliveries
- Damaged items tracking
- Automatic inventory adjustments for accepted quantities
- Exception reporting
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Sequence

from app.application.purchases.ports import PurchaseRepository
from app.application.inventory.ports import InventoryMovementRepository
from app.application.catalog.ports import ProductRepository
from app.domain.common.errors import NotFoundError, ValidationError
from app.domain.inventory import InventoryMovement, MovementDirection
from app.domain.purchases import (
    PurchaseOrderReceiving,
    ReceivingLineItem,
    ReceivingExceptionType,
    ReceivingStatus,
)


@dataclass(slots=True)
class ReceivingLineInput:
    """Input for a single receiving line."""
    purchase_order_item_id: str
    product_id: str
    quantity_ordered: int
    quantity_received: int
    quantity_damaged: int = 0
    exception_notes: str | None = None


@dataclass(slots=True)
class ReceivePurchaseOrderInput:
    """Input for receiving a purchase order."""
    purchase_order_id: str
    lines: list[ReceivingLineInput]
    received_by_user_id: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class ReceivingResult:
    """Result of receiving a purchase order."""
    receiving: PurchaseOrderReceiving
    inventory_movements: list[InventoryMovement]
    
    # Summary metrics
    total_ordered: int
    total_received: int
    total_accepted: int
    total_damaged: int
    fill_rate: Decimal
    has_exceptions: bool
    exception_summary: dict[str, int]


class ReceivePurchaseOrderUseCase:
    """Use case for receiving purchase orders."""

    def __init__(
        self,
        purchase_repo: PurchaseRepository,
        product_repo: ProductRepository,
        inventory_repo: InventoryMovementRepository,
    ) -> None:
        self._purchase_repo = purchase_repo
        self._product_repo = product_repo
        self._inventory_repo = inventory_repo

    async def execute(self, data: ReceivePurchaseOrderInput) -> ReceivingResult:
        """Execute the receiving process.
        
        1. Validate purchase order exists
        2. Validate all line items
        3. Create receiving record with all lines
        4. Create inventory movements for accepted quantities
        5. Update purchase order received_at timestamp
        """
        # 1. Validate purchase order exists
        purchase_order = await self._purchase_repo.get_purchase(data.purchase_order_id)
        if not purchase_order:
            raise NotFoundError(
                f"Purchase order {data.purchase_order_id} not found",
                code="receiving.purchase_order_not_found",
            )

        # 2. Create receiving record
        receiving = PurchaseOrderReceiving.start(
            purchase_order_id=data.purchase_order_id,
            received_by_user_id=data.received_by_user_id,
            notes=data.notes,
        )

        # 3. Process each line
        inventory_movements: list[InventoryMovement] = []
        
        for line_input in data.lines:
            # Validate product exists
            product = await self._product_repo.get_by_id(line_input.product_id)
            if not product:
                raise ValidationError(
                    f"Product {line_input.product_id} not found",
                    code="receiving.product_not_found",
                )

            # Add receiving line
            receiving_line = receiving.add_line(
                purchase_order_item_id=line_input.purchase_order_item_id,
                product_id=line_input.product_id,
                quantity_ordered=line_input.quantity_ordered,
                quantity_received=line_input.quantity_received,
                quantity_damaged=line_input.quantity_damaged,
                exception_notes=line_input.exception_notes,
            )

            # Create inventory movement for accepted quantity
            if receiving_line.quantity_accepted > 0:
                movement = InventoryMovement.record(
                    product_id=line_input.product_id,
                    quantity=receiving_line.quantity_accepted,
                    direction=MovementDirection.IN,
                    reason="purchase",
                    reference=f"PO:{data.purchase_order_id}",
                )
                await self._inventory_repo.add(movement)
                inventory_movements.append(movement)

        # 4. Complete receiving
        receiving.complete()

        # 5. Return result
        return ReceivingResult(
            receiving=receiving,
            inventory_movements=inventory_movements,
            total_ordered=receiving.total_ordered,
            total_received=receiving.total_received,
            total_accepted=receiving.total_accepted,
            total_damaged=receiving.total_damaged,
            fill_rate=receiving.fill_rate,
            has_exceptions=receiving.has_exceptions,
            exception_summary=receiving.exception_summary,
        )
