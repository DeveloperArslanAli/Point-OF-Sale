"""
Inventory event handler for WebSocket notifications.

Publishes real-time events for low stock, out of stock, and inventory updates.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
import structlog

from app.domain.inventory.movement import StockLevel
from app.core.settings import get_settings
from app.infrastructure.websocket.event_dispatcher import get_event_dispatcher
from app.infrastructure.websocket.events import (
    WebSocketEvent,
    EventType,
    InventoryEvent,
    ABCClassificationEvent,
    ReorderAlertEvent,
    ForecastAlertEvent,
    DeadStockAlertEvent,
)

logger = structlog.get_logger(__name__)
_settings = get_settings()


def _now() -> datetime:
    return datetime.now(UTC)


class InventoryEventHandler:
    """Handles inventory-related WebSocket events."""

    # Track last alert timestamps per product to avoid spamming listeners
    _last_alert_at: dict[str, datetime] = {}

    @classmethod
    def _is_throttled(cls, product_id: str) -> bool:
        cooldown_minutes = getattr(_settings, "ALERT_COOLDOWN_MINUTES", 5) or 0
        if cooldown_minutes <= 0:
            return False

        last = cls._last_alert_at.get(product_id)
        if last is None:
            return False

        return (_now() - last).total_seconds() < cooldown_minutes * 60

    @classmethod
    def _mark_alert(cls, product_id: str) -> None:
        cls._last_alert_at[product_id] = _now()

    @staticmethod
    async def publish_low_stock_alert(
        product_id: str,
        product_name: str,
        sku: str,
        current_quantity: Decimal,
        threshold: Decimal,
        location: str | None = None,
        tenant_id: str = "default",
    ) -> None:
        """
        Publish low stock alert event.

        Args:
            product_id: Product identifier
            product_name: Product name
            sku: Product SKU
            current_quantity: Current stock quantity
            threshold: Low stock threshold
            location: Optional location
            tenant_id: Tenant identifier
        """
        try:
            if InventoryEventHandler._is_throttled(product_id):
                logger.debug(
                    "low_stock_alert_throttled",
                    product_id=product_id,
                    sku=sku,
                )
                return

            dispatcher = get_event_dispatcher()

            payload = InventoryEvent(
                product_id=product_id,
                product_name=product_name,
                sku=sku,
                current_quantity=current_quantity,
                threshold=threshold,
                location=location,
                alert_type="low_stock",
            )

            event = WebSocketEvent(
                type=EventType.INVENTORY_LOW_STOCK,
                tenant_id=tenant_id,
                payload=payload.model_dump(),
            )

            # Broadcast to all users in tenant
            await dispatcher.publish_event(event, tenant_id=tenant_id)

            # Also notify managers/admins specifically
            await dispatcher.publish_to_role(
                event=event,
                tenant_id=tenant_id,
                role="manager",
            )

            InventoryEventHandler._mark_alert(product_id)
            logger.warning(
                "low_stock_alert_published",
                product_id=product_id,
                sku=sku,
                current_quantity=str(current_quantity),
                threshold=str(threshold),
                tenant_id=tenant_id,
            )

        except Exception as e:
            logger.error(
                "low_stock_alert_failed",
                product_id=product_id,
                error=str(e),
                exc_info=True,
            )

    @staticmethod
    async def publish_out_of_stock_alert(
        product_id: str,
        product_name: str,
        sku: str,
        location: str | None = None,
        tenant_id: str = "default",
    ) -> None:
        """
        Publish out of stock alert event.

        Args:
            product_id: Product identifier
            product_name: Product name
            sku: Product SKU
            location: Optional location
            tenant_id: Tenant identifier
        """
        try:
            if InventoryEventHandler._is_throttled(product_id):
                logger.debug(
                    "out_of_stock_alert_throttled",
                    product_id=product_id,
                    sku=sku,
                )
                return

            dispatcher = get_event_dispatcher()

            payload = InventoryEvent(
                product_id=product_id,
                product_name=product_name,
                sku=sku,
                current_quantity=Decimal("0"),
                location=location,
                alert_type="out_of_stock",
            )

            event = WebSocketEvent(
                type=EventType.INVENTORY_OUT_OF_STOCK,
                tenant_id=tenant_id,
                payload=payload.model_dump(),
            )

            # Critical alert - broadcast to everyone
            await dispatcher.publish_event(event, tenant_id=tenant_id)

            InventoryEventHandler._mark_alert(product_id)
            logger.error(
                "out_of_stock_alert_published",
                product_id=product_id,
                sku=sku,
                tenant_id=tenant_id,
            )

        except Exception as e:
            logger.error(
                "out_of_stock_alert_failed",
                product_id=product_id,
                error=str(e),
                exc_info=True,
            )

    @staticmethod
    async def publish_inventory_updated(
        product_id: str,
        product_name: str,
        sku: str,
        new_quantity: Decimal,
        location: str | None = None,
        tenant_id: str = "default",
    ) -> None:
        """
        Publish inventory updated event.

        Args:
            product_id: Product identifier
            product_name: Product name
            sku: Product SKU
            new_quantity: New stock quantity
            location: Optional location
            tenant_id: Tenant identifier
        """
        try:
            dispatcher = get_event_dispatcher()

            payload = InventoryEvent(
                product_id=product_id,
                product_name=product_name,
                sku=sku,
                current_quantity=new_quantity,
                location=location,
                alert_type="updated",
            )

            event = WebSocketEvent(
                type=EventType.INVENTORY_UPDATED,
                tenant_id=tenant_id,
                payload=payload.model_dump(),
            )

            # Broadcast to all users
            await dispatcher.publish_event(event, tenant_id=tenant_id)

            logger.info(
                "inventory_updated_event_published",
                product_id=product_id,
                sku=sku,
                new_quantity=str(new_quantity),
                tenant_id=tenant_id,
            )

        except Exception as e:
            logger.error(
                "inventory_updated_event_failed",
                product_id=product_id,
                error=str(e),
                exc_info=True,
            )

    @staticmethod
    async def check_and_publish_stock_alerts(
        stock_level: StockLevel,
        product_name: str,
        sku: str,
        low_stock_threshold: Decimal = Decimal("10"),
        tenant_id: str = "default",
    ) -> None:
        """
        Check stock level and publish appropriate alerts.

        Args:
            stock_level: StockLevel entity
            product_name: Product name
            sku: Product SKU
            low_stock_threshold: Threshold for low stock alerts
            tenant_id: Tenant identifier
        """
        quantity = Decimal(str(stock_level.quantity_on_hand))
        
        if quantity <= Decimal("0"):
            await InventoryEventHandler.publish_out_of_stock_alert(
                product_id=str(stock_level.product_id),
                product_name=product_name,
                sku=sku,
                tenant_id=tenant_id,
            )
        elif quantity <= low_stock_threshold:
            await InventoryEventHandler.publish_low_stock_alert(
                product_id=str(stock_level.product_id),
                product_name=product_name,
                sku=sku,
                current_quantity=quantity,
                threshold=low_stock_threshold,
                tenant_id=tenant_id,
            )

    # ==================== ABC Classification Alerts ====================

    @staticmethod
    async def publish_abc_classification_changed(
        product_id: str,
        product_name: str,
        sku: str,
        old_classification: str | None,
        new_classification: str,
        revenue_contribution: Decimal,
        tenant_id: str = "default",
    ) -> None:
        """
        Publish ABC classification change alert.

        Args:
            product_id: Product identifier
            product_name: Product name
            sku: Product SKU
            old_classification: Previous ABC class (None for new)
            new_classification: New ABC class (A, B, or C)
            revenue_contribution: Product's contribution to revenue
            tenant_id: Tenant identifier
        """
        try:
            dispatcher = get_event_dispatcher()

            # Determine reason
            if old_classification is None:
                reason = "initial"
            elif old_classification < new_classification:
                reason = "downgrade"  # A->B or B->C
            else:
                reason = "upgrade"  # C->B or B->A

            payload = ABCClassificationEvent(
                product_id=product_id,
                product_name=product_name,
                sku=sku,
                old_classification=old_classification or "N/A",
                new_classification=new_classification,
                revenue_contribution=revenue_contribution,
                reason=reason,
            )

            event = WebSocketEvent(
                type=EventType.INVENTORY_ABC_CHANGED,
                tenant_id=tenant_id,
                payload=payload.model_dump(),
            )

            # Notify managers and inventory staff
            await dispatcher.publish_to_role(
                event=event,
                tenant_id=tenant_id,
                role="manager",
            )

            logger.info(
                "abc_classification_changed",
                product_id=product_id,
                sku=sku,
                old=old_classification,
                new=new_classification,
                reason=reason,
            )

        except Exception as e:
            logger.error(
                "abc_classification_alert_failed",
                product_id=product_id,
                error=str(e),
                exc_info=True,
            )

    # ==================== Reorder Point Alerts ====================

    @staticmethod
    async def publish_reorder_alert(
        product_id: str,
        product_name: str,
        sku: str,
        current_quantity: Decimal,
        reorder_point: Decimal,
        suggested_order_qty: Decimal,
        days_until_stockout: int,
        tenant_id: str = "default",
    ) -> None:
        """
        Publish reorder point alert.

        Args:
            product_id: Product identifier
            product_name: Product name
            sku: Product SKU
            current_quantity: Current stock level
            reorder_point: Configured reorder point
            suggested_order_qty: Recommended order quantity
            days_until_stockout: Estimated days until stockout
            tenant_id: Tenant identifier
        """
        try:
            if InventoryEventHandler._is_throttled(product_id):
                return

            dispatcher = get_event_dispatcher()

            # Determine priority
            if days_until_stockout <= 3:
                priority = "critical"
            elif days_until_stockout <= 7:
                priority = "high"
            else:
                priority = "medium"

            payload = ReorderAlertEvent(
                product_id=product_id,
                product_name=product_name,
                sku=sku,
                current_quantity=current_quantity,
                reorder_point=reorder_point,
                suggested_order_qty=suggested_order_qty,
                days_until_stockout=days_until_stockout,
                priority=priority,
            )

            event = WebSocketEvent(
                type=EventType.INVENTORY_REORDER_ALERT,
                tenant_id=tenant_id,
                payload=payload.model_dump(),
            )

            # Critical alerts go to everyone, others to inventory/managers
            if priority == "critical":
                await dispatcher.publish_event(event, tenant_id=tenant_id)
            else:
                await dispatcher.publish_to_role(
                    event=event,
                    tenant_id=tenant_id,
                    role="inventory",
                )

            InventoryEventHandler._mark_alert(product_id)
            logger.warning(
                "reorder_alert_published",
                product_id=product_id,
                sku=sku,
                days_until_stockout=days_until_stockout,
                priority=priority,
            )

        except Exception as e:
            logger.error(
                "reorder_alert_failed",
                product_id=product_id,
                error=str(e),
                exc_info=True,
            )

    # ==================== Forecast Alerts ====================

    @staticmethod
    async def publish_forecast_alert(
        product_id: str,
        product_name: str,
        sku: str,
        forecast_period_days: int,
        predicted_demand: Decimal,
        current_stock: Decimal,
        stock_coverage_days: int,
        confidence: float,
        trend: str,
        tenant_id: str = "default",
    ) -> None:
        """
        Publish demand forecast alert.

        Args:
            product_id: Product identifier
            product_name: Product name
            sku: Product SKU
            forecast_period_days: Forecast horizon in days
            predicted_demand: Predicted demand quantity
            current_stock: Current stock quantity
            stock_coverage_days: Days current stock will last
            confidence: Forecast confidence (0-1)
            trend: Demand trend (increasing, stable, decreasing)
            tenant_id: Tenant identifier
        """
        try:
            dispatcher = get_event_dispatcher()

            # Determine recommendation
            if stock_coverage_days <= 3:
                recommendation = "order_now"
            elif stock_coverage_days <= 7:
                recommendation = "order_soon"
            else:
                recommendation = "adequate"

            payload = ForecastAlertEvent(
                product_id=product_id,
                product_name=product_name,
                sku=sku,
                forecast_period_days=forecast_period_days,
                predicted_demand=predicted_demand,
                current_stock=current_stock,
                stock_coverage_days=stock_coverage_days,
                recommendation=recommendation,
                confidence=confidence,
                trend=trend,
            )

            event = WebSocketEvent(
                type=EventType.INVENTORY_FORECAST_ALERT,
                tenant_id=tenant_id,
                payload=payload.model_dump(),
            )

            # Only send alerts for actionable recommendations
            if recommendation in ("order_now", "order_soon"):
                await dispatcher.publish_to_role(
                    event=event,
                    tenant_id=tenant_id,
                    role="manager",
                )

                logger.info(
                    "forecast_alert_published",
                    product_id=product_id,
                    sku=sku,
                    recommendation=recommendation,
                    stock_coverage_days=stock_coverage_days,
                )

        except Exception as e:
            logger.error(
                "forecast_alert_failed",
                product_id=product_id,
                error=str(e),
                exc_info=True,
            )

    # ==================== Dead Stock Alerts ====================

    @staticmethod
    async def publish_dead_stock_alert(
        product_id: str,
        product_name: str,
        sku: str,
        current_quantity: Decimal,
        days_without_sale: int,
        inventory_value: Decimal,
        last_sale_date: datetime | None = None,
        tenant_id: str = "default",
    ) -> None:
        """
        Publish dead stock alert.

        Args:
            product_id: Product identifier
            product_name: Product name
            sku: Product SKU
            current_quantity: Current stock quantity
            days_without_sale: Days since last sale
            inventory_value: Value of stuck inventory
            last_sale_date: Date of last sale
            tenant_id: Tenant identifier
        """
        try:
            dispatcher = get_event_dispatcher()

            # Determine recommendation based on severity
            if days_without_sale >= 180:
                recommendation = "liquidate"
            elif days_without_sale >= 120:
                recommendation = "donate"
            elif days_without_sale >= 90:
                recommendation = "bundle"
            else:
                recommendation = "markdown"

            payload = DeadStockAlertEvent(
                product_id=product_id,
                product_name=product_name,
                sku=sku,
                current_quantity=current_quantity,
                days_without_sale=days_without_sale,
                last_sale_date=last_sale_date,
                inventory_value=inventory_value,
                recommendation=recommendation,
            )

            event = WebSocketEvent(
                type=EventType.INVENTORY_DEAD_STOCK_ALERT,
                tenant_id=tenant_id,
                payload=payload.model_dump(),
            )

            # Notify managers for action
            await dispatcher.publish_to_role(
                event=event,
                tenant_id=tenant_id,
                role="manager",
            )

            logger.warning(
                "dead_stock_alert_published",
                product_id=product_id,
                sku=sku,
                days_without_sale=days_without_sale,
                inventory_value=str(inventory_value),
                recommendation=recommendation,
            )

        except Exception as e:
            logger.error(
                "dead_stock_alert_failed",
                product_id=product_id,
                error=str(e),
                exc_info=True,
            )
