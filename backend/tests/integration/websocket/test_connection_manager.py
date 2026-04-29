"""
Tests for WebSocket connection manager.
"""

import pytest
from fastapi import WebSocket
from unittest.mock import Mock, AsyncMock, patch

from app.infrastructure.websocket.connection_manager import ConnectionManager
from app.infrastructure.websocket.events import WebSocketEvent, EventType


@pytest.fixture
def connection_manager():
    """Fixture to provide a fresh ConnectionManager instance."""
    return ConnectionManager()


@pytest.fixture
def mock_websocket():
    """Fixture to provide a mock WebSocket."""
    ws = Mock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    @pytest.mark.asyncio
    async def test_connect_registers_connection(
        self, connection_manager, mock_websocket
    ):
        """Test that connect() registers a WebSocket connection."""
        await connection_manager.connect(
            websocket=mock_websocket,
            user_id="user123",
            tenant_id="tenant1",
            role="cashier",
            username="john_doe",
        )

        # Verify websocket.accept() was called
        mock_websocket.accept.assert_called_once()

        # Verify connection is registered
        assert "tenant1" in connection_manager._connections
        assert "user123" in connection_manager._connections["tenant1"]
        assert mock_websocket in connection_manager._connections["tenant1"]["user123"]

        # Verify metadata is stored
        conn_id = id(mock_websocket)
        assert conn_id in connection_manager._metadata
        metadata = connection_manager._metadata[conn_id]
        assert metadata["user_id"] == "user123"
        assert metadata["tenant_id"] == "tenant1"
        assert metadata["role"] == "cashier"
        assert metadata["username"] == "john_doe"

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(
        self, connection_manager, mock_websocket
    ):
        """Test that disconnect() removes a WebSocket connection."""
        # First connect
        await connection_manager.connect(
            websocket=mock_websocket,
            user_id="user123",
            tenant_id="tenant1",
            role="cashier",
            username="john_doe",
        )

        # Then disconnect
        await connection_manager.disconnect(mock_websocket)

        # Verify connection is removed
        assert "tenant1" not in connection_manager._connections or (
            "user123" not in connection_manager._connections.get("tenant1", {})
        )

        # Verify metadata is removed
        conn_id = id(mock_websocket)
        assert conn_id not in connection_manager._metadata

    @pytest.mark.asyncio
    async def test_broadcast_to_tenant(self, connection_manager):
        """Test broadcasting to all connections in a tenant."""
        # Setup multiple connections
        ws1, ws2, ws3 = Mock(spec=WebSocket), Mock(spec=WebSocket), Mock(spec=WebSocket)
        for ws in [ws1, ws2, ws3]:
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()

        await connection_manager.connect(ws1, "user1", "tenant1", "cashier", "john")
        await connection_manager.connect(ws2, "user2", "tenant1", "manager", "jane")
        await connection_manager.connect(ws3, "user3", "tenant2", "cashier", "bob")

        # Broadcast event to tenant1
        event = WebSocketEvent(
            type=EventType.SALE_CREATED,
            tenant_id="tenant1",
            payload={"sale_id": "123"},
        )
        await connection_manager.broadcast_to_tenant("tenant1", event)

        # Verify ws1 and ws2 received the event (tenant1)
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

        # Verify ws3 did NOT receive the event (tenant2)
        ws3.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_to_role(self, connection_manager):
        """Test broadcasting to specific role in a tenant."""
        # Setup connections with different roles
        ws1, ws2, ws3 = Mock(spec=WebSocket), Mock(spec=WebSocket), Mock(spec=WebSocket)
        for ws in [ws1, ws2, ws3]:
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()

        await connection_manager.connect(ws1, "user1", "tenant1", "cashier", "john")
        await connection_manager.connect(ws2, "user2", "tenant1", "manager", "jane")
        await connection_manager.connect(ws3, "user3", "tenant1", "admin", "alice")

        # Broadcast to managers only
        event = WebSocketEvent(
            type=EventType.INVENTORY_LOW_STOCK,
            tenant_id="tenant1",
            payload={"product_id": "456"},
        )
        await connection_manager.broadcast_to_role("tenant1", "manager", event)

        # Only ws2 (manager) should receive
        ws1.send_text.assert_not_called()
        ws2.send_text.assert_called_once()
        ws3.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_connected_users(self, connection_manager):
        """Test retrieving list of connected users."""
        # Setup connections
        ws1, ws2 = Mock(spec=WebSocket), Mock(spec=WebSocket)
        for ws in [ws1, ws2]:
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()

        await connection_manager.connect(ws1, "user1", "tenant1", "cashier", "john")
        await connection_manager.connect(ws2, "user2", "tenant1", "manager", "jane")

        # Get connected users
        users = connection_manager.get_connected_users("tenant1")

        # Verify
        assert len(users) == 2
        user_ids = {u["user_id"] for u in users}
        assert "user1" in user_ids
        assert "user2" in user_ids

    @pytest.mark.asyncio
    async def test_get_stats(self, connection_manager):
        """Test connection statistics."""
        # Setup connections
        ws1, ws2, ws3 = Mock(spec=WebSocket), Mock(spec=WebSocket), Mock(spec=WebSocket)
        for ws in [ws1, ws2, ws3]:
            ws.accept = AsyncMock()

        await connection_manager.connect(ws1, "user1", "tenant1", "cashier", "john")
        await connection_manager.connect(ws2, "user2", "tenant1", "manager", "jane")
        await connection_manager.connect(ws3, "user3", "tenant2", "cashier", "bob")

        # Get stats
        stats = connection_manager.get_stats()

        # Verify
        assert stats["total_connections"] == 3
        assert stats["total_tenants"] == 2
        assert "tenant1" in stats["tenant_stats"]
        assert stats["tenant_stats"]["tenant1"]["users"] == 2
        assert stats["tenant_stats"]["tenant2"]["users"] == 1
