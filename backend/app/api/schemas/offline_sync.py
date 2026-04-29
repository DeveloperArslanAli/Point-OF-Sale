"""Offline sync API schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class OfflineQueueItemRequest(BaseModel):
    """Single offline action to replay."""

    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique key to prevent duplicate processing",
    )
    action_type: str = Field(
        ...,
        description="Action type: sale, refund, shift_start, shift_end, drawer_open, drawer_close, drawer_movement, inventory_adjustment",
    )
    payload: dict[str, Any] = Field(
        ...,
        description="Action-specific data payload",
    )
    created_offline_at: datetime | None = Field(
        default=None,
        description="When the action was performed offline (ISO 8601)",
    )


class OfflineSyncRequest(BaseModel):
    """Batch of offline actions to replay."""

    terminal_id: str = Field(..., min_length=1, max_length=50)
    items: list[OfflineQueueItemRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of offline actions to replay (max 100)",
    )


class OfflineItemResultOut(BaseModel):
    """Result of processing a single offline item."""

    idempotency_key: str
    status: str  # completed, failed, skipped
    error: str | None = None
    result_id: str | None = Field(
        default=None,
        description="ID of created resource (e.g., sale_id)",
    )
    model_config = ConfigDict(from_attributes=True)


class OfflineSyncResultOut(BaseModel):
    """Result of processing a sync batch."""

    batch_id: str
    terminal_id: str
    total_items: int
    completed_count: int
    failed_count: int
    skipped_count: int
    success_rate: float
    started_at: datetime
    completed_at: datetime | None
    results: list[OfflineItemResultOut]
    model_config = ConfigDict(from_attributes=True)


# Payload schemas for different action types


class OfflineSalePayload(BaseModel):
    """Payload for offline sale action."""

    currency: str = Field(default="USD", min_length=3, max_length=3)
    lines: list[dict[str, Any]] = Field(..., min_length=1)
    payments: list[dict[str, Any]] = Field(..., min_length=1)
    customer_id: str | None = None
    shift_id: str | None = None


class OfflineShiftStartPayload(BaseModel):
    """Payload for offline shift start action."""

    terminal_id: str
    drawer_session_id: str | None = None
    opening_cash: Decimal | None = None
    currency: str = "USD"


class OfflineShiftEndPayload(BaseModel):
    """Payload for offline shift end action."""

    shift_id: str
    closing_cash: Decimal | None = None


class OfflineDrawerOpenPayload(BaseModel):
    """Payload for offline drawer open action."""

    terminal_id: str
    opening_amount: Decimal
    currency: str = "USD"


class OfflineDrawerClosePayload(BaseModel):
    """Payload for offline drawer close action."""

    session_id: str
    closing_amount: Decimal


class OfflineDrawerMovementPayload(BaseModel):
    """Payload for offline drawer movement action."""

    session_id: str
    movement_type: str
    amount: Decimal
    notes: str | None = None
