"""Purchase order receiving domain entities.

Handles receiving of purchase orders with support for:
- Partial deliveries
- Damaged items
- Over/under shipments
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from app.domain.common.identifiers import new_ulid
from app.domain.common.errors import ValidationError


class ReceivingExceptionType(str, Enum):
    """Types of receiving exceptions."""
    PARTIAL_DELIVERY = "partial_delivery"  # Less than ordered received
    OVER_DELIVERY = "over_delivery"  # More than ordered received
    DAMAGED = "damaged"  # Items received but damaged
    MISSING = "missing"  # Items not received at all
    WRONG_ITEM = "wrong_item"  # Different item received
    QUALITY_ISSUE = "quality_issue"  # Quality doesn't meet standards


class ReceivingStatus(str, Enum):
    """Status of purchase order receiving."""
    PENDING = "pending"  # Not yet received
    PARTIAL = "partial"  # Partially received
    COMPLETE = "complete"  # Fully received
    COMPLETE_WITH_EXCEPTIONS = "complete_with_exceptions"  # Received with issues
    CANCELLED = "cancelled"  # Receiving cancelled


@dataclass(slots=True)
class ReceivingLineItem:
    """Individual line item in a receiving record."""
    id: str
    purchase_order_item_id: str
    product_id: str
    
    # Quantities
    quantity_ordered: int
    quantity_received: int
    quantity_damaged: int = 0
    quantity_accepted: int = 0  # quantity_received - quantity_damaged
    
    # Exception tracking
    exception_type: ReceivingExceptionType | None = None
    exception_notes: str | None = None
    
    # Timestamps
    received_at: datetime | None = None

    def __post_init__(self) -> None:
        """Calculate accepted quantity."""
        self.quantity_accepted = max(0, self.quantity_received - self.quantity_damaged)
        
        # Determine exception type if any
        if self.quantity_received == 0 and self.quantity_ordered > 0:
            self.exception_type = ReceivingExceptionType.MISSING
        elif self.quantity_received < self.quantity_ordered:
            self.exception_type = ReceivingExceptionType.PARTIAL_DELIVERY
        elif self.quantity_received > self.quantity_ordered:
            self.exception_type = ReceivingExceptionType.OVER_DELIVERY
        elif self.quantity_damaged > 0:
            self.exception_type = ReceivingExceptionType.DAMAGED

    @staticmethod
    def create(
        *,
        purchase_order_item_id: str,
        product_id: str,
        quantity_ordered: int,
        quantity_received: int,
        quantity_damaged: int = 0,
        exception_notes: str | None = None,
    ) -> ReceivingLineItem:
        """Create a new receiving line item."""
        if quantity_received < 0:
            raise ValidationError(
                "quantity_received cannot be negative",
                code="receiving.invalid_quantity_received"
            )
        if quantity_damaged < 0:
            raise ValidationError(
                "quantity_damaged cannot be negative",
                code="receiving.invalid_quantity_damaged"
            )
        if quantity_damaged > quantity_received:
            raise ValidationError(
                "quantity_damaged cannot exceed quantity_received",
                code="receiving.damaged_exceeds_received"
            )
        
        return ReceivingLineItem(
            id=new_ulid(),
            purchase_order_item_id=purchase_order_item_id,
            product_id=product_id,
            quantity_ordered=quantity_ordered,
            quantity_received=quantity_received,
            quantity_damaged=quantity_damaged,
            exception_notes=exception_notes,
            received_at=datetime.now(UTC),
        )


@dataclass(slots=True)
class PurchaseOrderReceiving:
    """Record of receiving a purchase order."""
    id: str
    purchase_order_id: str
    
    # Line items
    items: list[ReceivingLineItem] = field(default_factory=list)
    
    # Status
    status: ReceivingStatus = ReceivingStatus.PENDING
    
    # Timestamps
    received_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    # Receiver info
    received_by_user_id: str | None = None
    
    # Notes
    notes: str | None = None

    @staticmethod
    def start(
        *,
        purchase_order_id: str,
        received_by_user_id: str | None = None,
        notes: str | None = None,
    ) -> PurchaseOrderReceiving:
        """Start a new receiving record for a purchase order."""
        if not purchase_order_id:
            raise ValidationError(
                "purchase_order_id is required",
                code="receiving.invalid_purchase_order_id"
            )
        return PurchaseOrderReceiving(
            id=new_ulid(),
            purchase_order_id=purchase_order_id,
            received_by_user_id=received_by_user_id,
            notes=notes,
        )

    def add_line(
        self,
        *,
        purchase_order_item_id: str,
        product_id: str,
        quantity_ordered: int,
        quantity_received: int,
        quantity_damaged: int = 0,
        exception_notes: str | None = None,
    ) -> ReceivingLineItem:
        """Add a receiving line item."""
        item = ReceivingLineItem.create(
            purchase_order_item_id=purchase_order_item_id,
            product_id=product_id,
            quantity_ordered=quantity_ordered,
            quantity_received=quantity_received,
            quantity_damaged=quantity_damaged,
            exception_notes=exception_notes,
        )
        self.items.append(item)
        return item

    def complete(self) -> None:
        """Mark receiving as complete and determine final status."""
        self.received_at = datetime.now(UTC)
        
        has_exceptions = any(item.exception_type is not None for item in self.items)
        all_received = all(
            item.quantity_accepted >= item.quantity_ordered 
            for item in self.items
        )
        
        if all_received and not has_exceptions:
            self.status = ReceivingStatus.COMPLETE
        elif all_received and has_exceptions:
            self.status = ReceivingStatus.COMPLETE_WITH_EXCEPTIONS
        else:
            self.status = ReceivingStatus.PARTIAL

    @property
    def total_ordered(self) -> int:
        """Total quantity ordered across all lines."""
        return sum(item.quantity_ordered for item in self.items)

    @property
    def total_received(self) -> int:
        """Total quantity received across all lines."""
        return sum(item.quantity_received for item in self.items)

    @property
    def total_accepted(self) -> int:
        """Total quantity accepted (not damaged) across all lines."""
        return sum(item.quantity_accepted for item in self.items)

    @property
    def total_damaged(self) -> int:
        """Total quantity damaged across all lines."""
        return sum(item.quantity_damaged for item in self.items)

    @property
    def has_exceptions(self) -> bool:
        """Whether receiving has any exceptions."""
        return any(item.exception_type is not None for item in self.items)

    @property
    def exception_summary(self) -> dict[str, int]:
        """Summary count of exceptions by type."""
        summary: dict[str, int] = {}
        for item in self.items:
            if item.exception_type:
                key = item.exception_type.value
                summary[key] = summary.get(key, 0) + 1
        return summary

    @property
    def fill_rate(self) -> Decimal:
        """Percentage of order fulfilled (accepted/ordered)."""
        if self.total_ordered == 0:
            return Decimal("100.00")
        return (Decimal(self.total_accepted) / Decimal(self.total_ordered) * 100).quantize(Decimal("0.01"))
