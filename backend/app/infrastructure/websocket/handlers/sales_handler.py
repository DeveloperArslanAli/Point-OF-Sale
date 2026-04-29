"""
Sales event handler for WebSocket notifications.

Publishes real-time events when sales are created, completed, or voided.
"""

from decimal import Decimal
from datetime import datetime
import structlog

from app.domain.sales.entities import Sale
from app.infrastructure.websocket.event_dispatcher import get_event_dispatcher
from app.infrastructure.websocket.events import (
    WebSocketEvent,
    EventType,
    SalesEvent,
)

logger = structlog.get_logger(__name__)


class SalesEventHandler:
    """Handles sales-related WebSocket events."""

    @staticmethod
    async def publish_sale_created(
        sale: Sale,
        cashier_id: str,
        cashier_name: str,
        customer_name: str | None = None,
        tenant_id: str = "default",
    ) -> None:
        """
        Publish sale created event.

        Args:
            sale: Sale entity
            cashier_name: Cashier username
            customer_name: Optional customer name
            tenant_id: Tenant identifier
        """
        try:
            dispatcher = get_event_dispatcher()

            payload = SalesEvent(
                sale_id=str(sale.id),
                total_amount=sale.total_amount.amount,
                items_count=len(sale.items),
                cashier_id=cashier_id,
                cashier_name=cashier_name,
                customer_id=str(sale.customer_id) if sale.customer_id else None,
                customer_name=customer_name,
                status="pending",
                created_at=sale.created_at,
            )

            event = WebSocketEvent(
                type=EventType.SALE_CREATED,
                tenant_id=tenant_id,
                payload=payload.model_dump(),
            )

            await dispatcher.publish_event(event, tenant_id=tenant_id)

            # Also notify managers/admins
            await dispatcher.publish_to_role(
                event=event,
                tenant_id=tenant_id,
                role="manager",
            )
            await dispatcher.publish_to_role(
                event=event,
                tenant_id=tenant_id,
                role="admin",
            )

            logger.info(
                "sale_created_event_published",
                sale_id=str(sale.id),
                tenant_id=tenant_id,
                total=str(sale.total_amount.amount),
            )

        except Exception as e:
            logger.error(
                "sale_created_event_failed",
                sale_id=str(sale.id),
                error=str(e),
                exc_info=True,
            )

    @staticmethod
    async def publish_sale_completed(
        sale: Sale,
        cashier_id: str,
        cashier_name: str,
        customer_name: str | None = None,
        tenant_id: str = "default",
    ) -> None:
        """
        Publish sale completed event.

        Args:
            sale: Completed sale entity
            cashier_name: Cashier username
            customer_name: Optional customer name
            tenant_id: Tenant identifier
        """
        try:
            dispatcher = get_event_dispatcher()

            payload = SalesEvent(
                sale_id=str(sale.id),
                total_amount=sale.total_amount.amount,
                items_count=len(sale.items),
                cashier_id=cashier_id,
                cashier_name=cashier_name,
                customer_id=str(sale.customer_id) if sale.customer_id else None,
                customer_name=customer_name,
                status="completed",
                created_at=sale.created_at,
            )

            event = WebSocketEvent(
                type=EventType.SALE_COMPLETED,
                tenant_id=tenant_id,
                payload=payload.model_dump(),
            )

            await dispatcher.publish_event(event, tenant_id=tenant_id)

            logger.info(
                "sale_completed_event_published",
                sale_id=str(sale.id),
                tenant_id=tenant_id,
            )

        except Exception as e:
            logger.error(
                "sale_completed_event_failed",
                sale_id=str(sale.id),
                error=str(e),
                exc_info=True,
            )

    @staticmethod
    async def publish_sale_voided(
        sale_id: str,
        total_amount: Decimal,
        reason: str,
        voided_by: str,
        tenant_id: str = "default",
    ) -> None:
        """
        Publish sale voided event.

        Args:
            sale_id: Sale identifier
            total_amount: Sale total
            reason: Void reason
            voided_by: User who voided the sale
            tenant_id: Tenant identifier
        """
        try:
            dispatcher = get_event_dispatcher()

            event = WebSocketEvent(
                type=EventType.SALE_VOIDED,
                tenant_id=tenant_id,
                payload={
                    "sale_id": sale_id,
                    "total_amount": str(total_amount),
                    "reason": reason,
                    "voided_by": voided_by,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            # Notify all managers/admins (important event)
            await dispatcher.publish_to_role(
                event=event,
                tenant_id=tenant_id,
                role="manager",
            )
            await dispatcher.publish_to_role(
                event=event,
                tenant_id=tenant_id,
                role="admin",
            )

            logger.warning(
                "sale_voided_event_published",
                sale_id=sale_id,
                tenant_id=tenant_id,
                reason=reason,
            )

        except Exception as e:
            logger.error(
                "sale_voided_event_failed",
                sale_id=sale_id,
                error=str(e),
                exc_info=True,
            )
