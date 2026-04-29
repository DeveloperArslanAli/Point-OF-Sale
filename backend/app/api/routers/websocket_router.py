"""
WebSocket router for real-time communication.

Provides WebSocket endpoint for client connections with JWT authentication.
"""

from typing import Optional
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
import jwt
from jwt.exceptions import DecodeError, InvalidTokenError

from app.core.settings import get_settings
from app.infrastructure.websocket.connection_manager import connection_manager
from app.infrastructure.websocket.event_dispatcher import get_event_dispatcher

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time communication.

    Authentication:
        - Pass JWT token as query parameter: /ws?token=<jwt_token>
        - Token must be valid and not expired

    Events:
        - Receive real-time updates for sales, inventory, prices, presence
        - Events are filtered by tenant_id from the JWT token
        - Role-based event filtering applies automatically

    Usage:
        ```javascript
        const ws = new WebSocket(`ws://localhost:8000/api/v1/ws?token=${accessToken}`);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Event:', data.type, data.payload);
        };
        ```
    """
    # Validate token
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning("websocket_connection_rejected_no_token")
        return

    try:
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id", "default")
        role: str = payload.get("role", "user")
        username: str = payload.get("username", "unknown")

        if user_id is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            logger.warning("websocket_connection_rejected_invalid_token")
            return

    except (DecodeError, InvalidTokenError) as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning("websocket_connection_rejected_jwt_error", error=str(e))
        return

    # Connect to connection manager
    await connection_manager.connect(
        websocket=websocket,
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        username=username,
    )

    try:
        # Keep connection alive and handle client messages
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            # Echo back for now (can add client-to-server events later)
            logger.debug(
                "websocket_message_received",
                user_id=user_id,
                tenant_id=tenant_id,
                data=data,
            )

            # Optional: Handle client commands
            # For now, just acknowledge
            await websocket.send_json(
                {
                    "type": "ack",
                    "message": "Message received",
                }
            )

    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(
            "websocket_error",
            user_id=user_id,
            tenant_id=tenant_id,
            error=str(e),
            exc_info=True,
        )
        await connection_manager.disconnect(websocket)


@router.get("/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.

    Returns:
        - Total connections
        - Per-tenant breakdown
        - Connected users count
    """
    return connection_manager.get_stats()


@router.get("/connected-users")
async def get_connected_users(
    tenant_id: str = Query(..., description="Tenant ID to query"),
):
    """
    Get list of currently connected users for a tenant.

    Returns user metadata including role and connection time.
    """
    return {
        "tenant_id": tenant_id,
        "users": connection_manager.get_connected_users(tenant_id),
    }
