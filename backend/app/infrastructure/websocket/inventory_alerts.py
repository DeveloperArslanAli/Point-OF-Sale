"""WebSocket inventory alert broadcasting service.

Broadcasts low-stock and out-of-stock events via WebSocket to connected clients.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.infrastructure.websocket.events import EventType, WebSocketEvent, InventoryEvent

if TYPE_CHECKING:
    from app.infrastructure.websocket.event_dispatcher import EventDispatcher

logger = structlog.get_logger(__name__)


async def broadcast_low_stock_alert(
    dispatcher: "EventDispatcher",
    tenant_id: str,
    product_id: str,
    product_name: str,
    sku: str,
    current_quantity: Decimal,
    reorder_point: Decimal,
    days_until_stockout: int | None = None,
    recommended_order: Decimal | None = None,
) -> bool:
    """Broadcast a low stock alert via WebSocket.
    
    Args:
        dispatcher: EventDispatcher instance
        tenant_id: Tenant ID for filtering
        product_id: Product ID
        product_name: Product name for display
        sku: Product SKU
        current_quantity: Current stock level
        reorder_point: Reorder threshold
        days_until_stockout: Estimated days until stockout
        recommended_order: Suggested reorder quantity
        
    Returns:
        True if broadcast succeeded
    """
    try:
        payload = InventoryEvent(
            product_id=product_id,
            product_name=product_name,
            sku=sku,
            current_quantity=current_quantity,
            threshold=reorder_point,
            alert_type="low_stock",
        ).model_dump()
        
        # Add extra context
        payload["days_until_stockout"] = days_until_stockout
        payload["recommended_order"] = str(recommended_order) if recommended_order else None
        payload["reorder_point"] = str(reorder_point)
        
        event = WebSocketEvent(
            type=EventType.INVENTORY_LOW_STOCK,
            tenant_id=tenant_id,
            payload=payload,
        )
        
        await dispatcher.publish(event)
        
        logger.info(
            "low_stock_alert_broadcast",
            product_id=product_id,
            sku=sku,
            tenant_id=tenant_id,
        )
        return True
        
    except Exception as e:
        logger.error(
            "low_stock_alert_broadcast_failed",
            product_id=product_id,
            error=str(e),
        )
        return False


async def broadcast_out_of_stock_alert(
    dispatcher: "EventDispatcher",
    tenant_id: str,
    product_id: str,
    product_name: str,
    sku: str,
    location: str | None = None,
) -> bool:
    """Broadcast an out of stock alert via WebSocket.
    
    Args:
        dispatcher: EventDispatcher instance
        tenant_id: Tenant ID for filtering
        product_id: Product ID
        product_name: Product name for display
        sku: Product SKU
        location: Optional location identifier
        
    Returns:
        True if broadcast succeeded
    """
    try:
        payload = InventoryEvent(
            product_id=product_id,
            product_name=product_name,
            sku=sku,
            current_quantity=Decimal("0"),
            location=location,
            alert_type="out_of_stock",
        ).model_dump()
        
        event = WebSocketEvent(
            type=EventType.INVENTORY_OUT_OF_STOCK,
            tenant_id=tenant_id,
            payload=payload,
        )
        
        await dispatcher.publish(event)
        
        logger.info(
            "out_of_stock_alert_broadcast",
            product_id=product_id,
            sku=sku,
            tenant_id=tenant_id,
        )
        return True
        
    except Exception as e:
        logger.error(
            "out_of_stock_alert_broadcast_failed",
            product_id=product_id,
            error=str(e),
        )
        return False


async def broadcast_multiple_low_stock_alerts(
    dispatcher: "EventDispatcher",
    tenant_id: str,
    items: list[dict],
) -> dict:
    """Broadcast multiple low stock alerts in batch.
    
    Args:
        dispatcher: EventDispatcher instance
        tenant_id: Tenant ID
        items: List of dicts with product_id, product_name, sku, 
               current_quantity, reorder_point, etc.
               
    Returns:
        Summary dict with broadcast count and failures
    """
    success_count = 0
    failure_count = 0
    
    for item in items:
        try:
            result = await broadcast_low_stock_alert(
                dispatcher=dispatcher,
                tenant_id=tenant_id,
                product_id=item["product_id"],
                product_name=item.get("product_name", item.get("name", "Unknown")),
                sku=item.get("sku", ""),
                current_quantity=Decimal(str(item.get("current_quantity", item.get("quantity_on_hand", 0)))),
                reorder_point=Decimal(str(item.get("reorder_point", 0))),
                days_until_stockout=item.get("days_until_stockout"),
                recommended_order=Decimal(str(item["recommended_order"])) if item.get("recommended_order") else None,
            )
            
            if result:
                success_count += 1
            else:
                failure_count += 1
                
        except Exception as e:
            logger.warning(
                "batch_low_stock_alert_item_failed",
                product_id=item.get("product_id"),
                error=str(e),
            )
            failure_count += 1
    
    logger.info(
        "batch_low_stock_alerts_completed",
        tenant_id=tenant_id,
        success_count=success_count,
        failure_count=failure_count,
        total=len(items),
    )
    
    return {
        "broadcast_count": success_count,
        "failure_count": failure_count,
        "total_items": len(items),
    }
