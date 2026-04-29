"""
WebSocket connection manager.

Manages active WebSocket connections with tenant/user/role awareness.
Provides broadcast capabilities and connection pooling.
"""

from typing import Dict, Set, Optional, List
from collections import defaultdict
import structlog
import json
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from .events import WebSocketEvent, EventType

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections with tenant/user/role awareness.

    Features:
    - Per-tenant connection isolation
    - Role-based broadcasting
    - User presence tracking
    - Automatic cleanup on disconnect
    """

    def __init__(self):
        # Active connections: {tenant_id: {user_id: [WebSocket, ...]}}
        self._connections: Dict[str, Dict[str, List[WebSocket]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # User metadata: {connection_id: {user_id, role, tenant_id, connected_at}}
        self._metadata: Dict[int, dict] = {}

        # Role to connections mapping: {tenant_id: {role: {connection_id, ...}}}
        self._role_index: Dict[str, Dict[str, Set[int]]] = defaultdict(
            lambda: defaultdict(set)
        )

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        tenant_id: str,
        role: str,
        username: str,
    ) -> None:
        """
        Accept and register a WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance
            user_id: User identifier
            tenant_id: Tenant identifier for isolation
            role: User role for targeted broadcasting
            username: Username for presence events
        """
        await websocket.accept()

        # Register connection
        self._connections[tenant_id][user_id].append(websocket)

        # Store metadata
        conn_id = id(websocket)
        self._metadata[conn_id] = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "username": username,
            "connected_at": datetime.utcnow(),
        }

        # Index by role
        self._role_index[tenant_id][role].add(conn_id)

        logger.info(
            "websocket_connected",
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            connection_id=conn_id,
        )

        # Broadcast presence event
        await self.broadcast_to_tenant(
            tenant_id=tenant_id,
            event=WebSocketEvent(
                type=EventType.USER_CONNECTED,
                tenant_id=tenant_id,
                payload={
                    "user_id": user_id,
                    "username": username,
                    "role": role,
                    "status": "online",
                },
            ),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection and broadcast presence event.

        Args:
            websocket: FastAPI WebSocket instance to remove
        """
        conn_id = id(websocket)
        metadata = self._metadata.get(conn_id)

        if not metadata:
            logger.warning("websocket_disconnect_unknown", connection_id=conn_id)
            return

        user_id = metadata["user_id"]
        tenant_id = metadata["tenant_id"]
        role = metadata["role"]
        username = metadata["username"]

        # Remove from connections
        if tenant_id in self._connections and user_id in self._connections[tenant_id]:
            user_connections = self._connections[tenant_id][user_id]
            if websocket in user_connections:
                user_connections.remove(websocket)

            # Clean up empty structures
            if not user_connections:
                del self._connections[tenant_id][user_id]
            if not self._connections[tenant_id]:
                del self._connections[tenant_id]

        # Remove from role index
        if tenant_id in self._role_index and role in self._role_index[tenant_id]:
            self._role_index[tenant_id][role].discard(conn_id)
            if not self._role_index[tenant_id][role]:
                del self._role_index[tenant_id][role]
            if not self._role_index[tenant_id]:
                del self._role_index[tenant_id]

        # Remove metadata
        del self._metadata[conn_id]

        logger.info(
            "websocket_disconnected",
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            connection_id=conn_id,
        )

        # Broadcast presence event
        await self.broadcast_to_tenant(
            tenant_id=tenant_id,
            event=WebSocketEvent(
                type=EventType.USER_DISCONNECTED,
                tenant_id=tenant_id,
                payload={
                    "user_id": user_id,
                    "username": username,
                    "role": role,
                    "status": "offline",
                },
            ),
        )

    async def send_personal_message(
        self, websocket: WebSocket, event: WebSocketEvent
    ) -> None:
        """
        Send a message to a specific WebSocket connection.

        Args:
            websocket: Target WebSocket connection
            event: Event to send
        """
        try:
            await websocket.send_text(event.model_dump_json())
        except Exception as e:
            logger.error(
                "websocket_send_failed",
                connection_id=id(websocket),
                error=str(e),
            )

    async def broadcast_to_user(
        self, user_id: str, tenant_id: str, event: WebSocketEvent
    ) -> None:
        """
        Broadcast message to all connections of a specific user.

        Args:
            user_id: Target user identifier
            tenant_id: Tenant identifier
            event: Event to broadcast
        """
        connections = self._connections.get(tenant_id, {}).get(user_id, [])

        for websocket in connections:
            await self.send_personal_message(websocket, event)

        logger.debug(
            "broadcast_to_user",
            user_id=user_id,
            tenant_id=tenant_id,
            event_type=event.type,
            connections_count=len(connections),
        )

    async def broadcast_to_tenant(
        self, tenant_id: str, event: WebSocketEvent
    ) -> None:
        """
        Broadcast message to all connections in a tenant.

        Args:
            tenant_id: Target tenant identifier
            event: Event to broadcast
        """
        tenant_connections = self._connections.get(tenant_id, {})
        count = 0

        for user_id, connections in tenant_connections.items():
            for websocket in connections:
                await self.send_personal_message(websocket, event)
                count += 1

        logger.debug(
            "broadcast_to_tenant",
            tenant_id=tenant_id,
            event_type=event.type,
            connections_count=count,
        )

    async def broadcast_to_role(
        self, tenant_id: str, role: str, event: WebSocketEvent
    ) -> None:
        """
        Broadcast message to all connections with a specific role in a tenant.

        Args:
            tenant_id: Target tenant identifier
            role: Target role (e.g., "admin", "manager", "cashier")
            event: Event to broadcast
        """
        conn_ids = self._role_index.get(tenant_id, {}).get(role, set())

        for conn_id in conn_ids:
            metadata = self._metadata.get(conn_id)
            if not metadata:
                continue

            user_id = metadata["user_id"]
            connections = self._connections.get(tenant_id, {}).get(user_id, [])

            for websocket in connections:
                if id(websocket) == conn_id:
                    await self.send_personal_message(websocket, event)

        logger.debug(
            "broadcast_to_role",
            tenant_id=tenant_id,
            role=role,
            event_type=event.type,
            connections_count=len(conn_ids),
        )

    def get_connected_users(self, tenant_id: str) -> List[dict]:
        """
        Get list of currently connected users in a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of user metadata dictionaries
        """
        tenant_connections = self._connections.get(tenant_id, {})
        users = []

        seen_users = set()
        for user_id in tenant_connections.keys():
            if user_id in seen_users:
                continue
            seen_users.add(user_id)

            # Find any connection for this user to get metadata
            connections = tenant_connections[user_id]
            if connections:
                conn_id = id(connections[0])
                metadata = self._metadata.get(conn_id)
                if metadata:
                    users.append(
                        {
                            "user_id": user_id,
                            "username": metadata["username"],
                            "role": metadata["role"],
                            "connected_at": metadata["connected_at"].isoformat(),
                            "connection_count": len(connections),
                        }
                    )

        return users

    def get_stats(self) -> dict:
        """
        Get connection statistics.

        Returns:
            Dictionary with connection counts and statistics
        """
        total_connections = sum(
            len(self._metadata) for _ in [None]  # Count all metadata entries
        )

        tenant_stats = {}
        for tenant_id, users in self._connections.items():
            user_count = len(users)
            conn_count = sum(len(conns) for conns in users.values())
            tenant_stats[tenant_id] = {
                "users": user_count,
                "connections": conn_count,
            }

        return {
            "total_connections": len(self._metadata),
            "total_tenants": len(self._connections),
            "tenant_stats": tenant_stats,
        }


# Global connection manager instance
connection_manager = ConnectionManager()
