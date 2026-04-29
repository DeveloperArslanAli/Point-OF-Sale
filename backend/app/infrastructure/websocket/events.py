"""
WebSocket event schemas and types.

Defines all real-time event types used across the system.
"""

from enum import Enum
from typing import Any, Optional
from datetime import datetime, UTC
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict, field_serializer


class EventType(str, Enum):
    """Event type enumeration for WebSocket messages."""

    # Sales events
    SALE_CREATED = "sale.created"
    SALE_VOIDED = "sale.voided"
    SALE_COMPLETED = "sale.completed"

    # Inventory events
    INVENTORY_LOW_STOCK = "inventory.low_stock"
    INVENTORY_OUT_OF_STOCK = "inventory.out_of_stock"
    INVENTORY_UPDATED = "inventory.updated"
    INVENTORY_ABC_CHANGED = "inventory.abc_changed"
    INVENTORY_REORDER_ALERT = "inventory.reorder_alert"
    INVENTORY_FORECAST_ALERT = "inventory.forecast_alert"
    INVENTORY_DEAD_STOCK_ALERT = "inventory.dead_stock"

    # Price events
    PRICE_CHANGED = "price.changed"
    BULK_PRICE_UPDATE = "price.bulk_update"

    # Presence events
    USER_CONNECTED = "presence.connected"
    USER_DISCONNECTED = "presence.disconnected"
    USER_STATUS_CHANGED = "presence.status_changed"

    # Import events
    IMPORT_STARTED = "import.started"
    IMPORT_COMPLETED = "import.completed"
    IMPORT_FAILED = "import.failed"

    # Return events
    RETURN_CREATED = "return.created"
    RETURN_APPROVED = "return.approved"

    # System events
    SYSTEM_ALERT = "system.alert"
    SYSTEM_MAINTENANCE = "system.maintenance"


class WebSocketEvent(BaseModel):
    """Base WebSocket event schema."""

    type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tenant_id: Optional[str] = None
    payload: dict[str, Any]
    model_config = ConfigDict()

    @field_serializer("timestamp")
    def _serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()

class SalesEvent(BaseModel):
    """Sales event payload."""

    sale_id: str
    total_amount: Decimal
    items_count: int
    cashier_id: str
    cashier_name: str
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    status: str  # "pending", "completed", "voided"
    created_at: datetime
    model_config = ConfigDict()

    @field_serializer("total_amount")
    def _serialize_total_amount(self, value: Decimal) -> str:
        return str(value)

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()


class InventoryEvent(BaseModel):
    """Inventory event payload."""

    product_id: str
    product_name: str
    sku: str
    current_quantity: Decimal
    threshold: Optional[Decimal] = None
    location: Optional[str] = None
    alert_type: str  # "low_stock", "out_of_stock", "updated"
    model_config = ConfigDict()

    @field_serializer("current_quantity")
    def _serialize_current_quantity(self, value: Decimal) -> str:
        return str(value)

    @field_serializer("threshold")
    def _serialize_threshold(self, value: Optional[Decimal]) -> Optional[str]:
        return str(value) if value is not None else None


class PriceChangeEvent(BaseModel):
    """Price change event payload."""

    product_id: str
    product_name: str
    old_price: Decimal
    new_price: Decimal
    changed_by: str
    reason: Optional[str] = None
    model_config = ConfigDict()

    @field_serializer("old_price", "new_price")
    def _serialize_prices(self, value: Decimal) -> str:
        return str(value)


class PresenceEvent(BaseModel):
    """User presence event payload."""

    user_id: str
    username: str
    role: str
    status: str  # "online", "offline", "away"
    terminal_id: Optional[str] = None


class ImportEvent(BaseModel):
    """Import job event payload."""

    job_id: str
    task_id: Optional[str] = None
    filename: str
    status: str  # "queued", "processing", "completed", "failed"
    processed_count: int = 0
    failed_count: int = 0
    total_count: int = 0


class ReturnEvent(BaseModel):
    """Return event payload."""

    return_id: str
    original_sale_id: str
    total_amount: Decimal
    items_count: int
    reason: Optional[str] = None
    processed_by: str
    status: str  # "pending", "approved", "rejected"
    model_config = ConfigDict()

    @field_serializer("total_amount")
    def _serialize_total_amount(self, value: Decimal) -> str:
        return str(value)


class SystemAlert(BaseModel):
    """System alert payload."""

    severity: str  # "info", "warning", "error", "critical"
    message: str
    details: Optional[dict[str, Any]] = None
    action_required: bool = False


class ABCClassificationEvent(BaseModel):
    """ABC classification change event payload."""

    product_id: str
    product_name: str
    sku: str
    old_classification: str  # "A", "B", "C", or None for new
    new_classification: str  # "A", "B", "C"
    revenue_contribution: Decimal
    reason: str  # "upgrade", "downgrade", "initial"
    model_config = ConfigDict()

    @field_serializer("revenue_contribution")
    def _serialize_revenue(self, value: Decimal) -> str:
        return str(value)


class ReorderAlertEvent(BaseModel):
    """Reorder point alert event payload."""

    product_id: str
    product_name: str
    sku: str
    current_quantity: Decimal
    reorder_point: Decimal
    suggested_order_qty: Decimal
    days_until_stockout: int
    priority: str  # "critical", "high", "medium"
    model_config = ConfigDict()

    @field_serializer("current_quantity", "reorder_point", "suggested_order_qty")
    def _serialize_decimals(self, value: Decimal) -> str:
        return str(value)


class ForecastAlertEvent(BaseModel):
    """Demand forecast alert event payload."""

    product_id: str
    product_name: str
    sku: str
    forecast_period_days: int
    predicted_demand: Decimal
    current_stock: Decimal
    stock_coverage_days: int
    recommendation: str  # "order_now", "order_soon", "adequate"
    confidence: float  # 0.0-1.0
    trend: str  # "increasing", "stable", "decreasing"
    model_config = ConfigDict()

    @field_serializer("predicted_demand", "current_stock")
    def _serialize_decimals(self, value: Decimal) -> str:
        return str(value)


class DeadStockAlertEvent(BaseModel):
    """Dead stock alert event payload."""

    product_id: str
    product_name: str
    sku: str
    current_quantity: Decimal
    days_without_sale: int
    last_sale_date: Optional[datetime] = None
    inventory_value: Decimal
    recommendation: str  # "markdown", "bundle", "liquidate", "donate"
    model_config = ConfigDict()

    @field_serializer("current_quantity", "inventory_value")
    def _serialize_decimals(self, value: Decimal) -> str:
        return str(value)

    @field_serializer("last_sale_date")
    def _serialize_last_sale(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None
