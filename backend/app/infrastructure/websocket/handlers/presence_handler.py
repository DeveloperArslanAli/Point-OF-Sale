"""
Presence event handler for WebSocket notifications.

Handles user online/offline status and presence updates.
Note: Most presence events are automatically handled by ConnectionManager.
This handler provides additional presence-related utilities.
"""

import structlog

from app.infrastructure.websocket.event_dispatcher import get_event_dispatcher
from app.infrastructure.websocket.events import (
    WebSocketEvent,
    EventType,
    PresenceEvent,
)

logger = structlog.get_logger(__name__)


class PresenceEventHandler:
    """Handles user presence-related WebSocket events."""

    @staticmethod
    async def publish_status_changed(
        user_id: str,
        username: str,
        role: str,
        status: str,
        terminal_id: str | None = None,
        tenant_id: str = "default",
    ) -> None:
        """
        Publish user status changed event.

        Args:
            user_id: User identifier
            username: Username
            role: User role
            status: New status ("online", "offline", "away", "busy")
            terminal_id: Optional terminal identifier
            tenant_id: Tenant identifier
        """
        try:
            dispatcher = get_event_dispatcher()

            payload = PresenceEvent(
                user_id=user_id,
                username=username,
                role=role,
                status=status,
                terminal_id=terminal_id,
            )

            event = WebSocketEvent(
                type=EventType.USER_STATUS_CHANGED,
                tenant_id=tenant_id,
                payload=payload.model_dump(),
            )

            await dispatcher.publish_event(event, tenant_id=tenant_id)

            logger.info(
                "presence_status_changed_published",
                user_id=user_id,
                status=status,
                tenant_id=tenant_id,
            )

        except Exception as e:
            logger.error(
                "presence_status_changed_failed",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
