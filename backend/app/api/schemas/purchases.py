from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.schemas.inventory import InventoryMovementOut
from app.domain.inventory import InventoryMovement
from app.domain.purchases import PurchaseOrder, PurchaseOrderItem


class PurchaseLineCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=26)
    quantity: int = Field(gt=0)
    unit_cost: Decimal = Field(gt=0)


class PurchaseCreate(BaseModel):
    supplier_id: str = Field(min_length=1, max_length=26)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    lines: list[PurchaseLineCreate]

    @field_validator("lines")
    @classmethod
    def ensure_lines_present(cls, value: list[PurchaseLineCreate]) -> list[PurchaseLineCreate]:
        if not value:
            raise ValueError("Purchase requires at least one line")
        return value


class PurchaseItemOut(BaseModel):
    id: str
    product_id: str
    quantity: int
    unit_cost: str
    line_total: str

    @classmethod
    def from_domain(cls, item: PurchaseOrderItem) -> PurchaseItemOut:
        return cls(
            id=item.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_cost=str(item.unit_cost.amount),
            line_total=str(item.line_total.amount),
        )


class PurchaseOut(BaseModel):
    id: str
    supplier_id: str
    currency: str
    total_amount: str
    total_quantity: int
    created_at: datetime
    received_at: datetime | None
    items: list[PurchaseItemOut]

    @classmethod
    def from_domain(cls, purchase: PurchaseOrder) -> PurchaseOut:
        return cls(
            id=purchase.id,
            supplier_id=purchase.supplier_id,
            currency=purchase.currency,
            total_amount=str(purchase.total_amount.amount),
            total_quantity=purchase.total_quantity,
            created_at=purchase.created_at,
            received_at=purchase.received_at,
            items=[PurchaseItemOut.from_domain(item) for item in purchase.iter_items()],
        )


class PurchaseRecordOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    purchase: PurchaseOut
    movements: list[InventoryMovementOut]

    @classmethod
    def build(cls, purchase: PurchaseOrder, movements: Sequence[InventoryMovement]) -> PurchaseRecordOut:
        movement_out = [InventoryMovementOut.model_validate(movement) for movement in movements]
        return cls(purchase=PurchaseOut.from_domain(purchase), movements=movement_out)


class PurchasePageMetaOut(BaseModel):
    page: int
    limit: int
    total: int
    pages: int


class PurchaseListOut(BaseModel):
    items: list[PurchaseOut]
    meta: PurchasePageMetaOut


# =============================================================================
# Receiving Schemas
# =============================================================================

class ReceivingLineCreate(BaseModel):
    """Input for receiving a single line item."""
    purchase_order_item_id: str = Field(min_length=1, max_length=26)
    product_id: str = Field(min_length=1, max_length=26)
    quantity_ordered: int = Field(ge=0)
    quantity_received: int = Field(ge=0)
    quantity_damaged: int = Field(default=0, ge=0)
    exception_notes: str | None = Field(default=None, max_length=500)


class ReceivePurchaseCreate(BaseModel):
    """Input for receiving a purchase order."""
    lines: list[ReceivingLineCreate]
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("lines")
    @classmethod
    def ensure_lines_present(cls, value: list[ReceivingLineCreate]) -> list[ReceivingLineCreate]:
        if not value:
            raise ValueError("Receiving requires at least one line")
        return value


class ReceivingLineOut(BaseModel):
    """Output for a receiving line item."""
    id: str
    purchase_order_item_id: str
    product_id: str
    quantity_ordered: int
    quantity_received: int
    quantity_damaged: int
    quantity_accepted: int
    exception_type: str | None
    exception_notes: str | None
    received_at: datetime | None


class ReceivingOut(BaseModel):
    """Output for a receiving record."""
    id: str
    purchase_order_id: str
    status: str
    received_at: datetime | None
    created_at: datetime
    received_by_user_id: str | None
    notes: str | None
    items: list[ReceivingLineOut]
    
    # Summary metrics
    total_ordered: int
    total_received: int
    total_accepted: int
    total_damaged: int
    fill_rate: Decimal = Field(decimal_places=2)
    has_exceptions: bool
    exception_summary: dict[str, int]


class ReceivingResultOut(BaseModel):
    """Result of receiving a purchase order."""
    receiving: ReceivingOut
    movements: list[InventoryMovementOut]

