"""
Tests for WebSocket event dispatcher.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import json

from app.infrastructure.websocket.connection_manager import ConnectionManager
from app.infrastructure.websocket.event_dispatcher import EventDispatcher
from app.infrastructure.websocket.events import WebSocketEvent, EventType


@pytest.fixture
def connection_manager():
    """Fixture to provide a ConnectionManager instance."""
    return ConnectionManager()


@pytest.mark.asyncio
class TestEventDispatcher:
    """Tests for EventDispatcher class."""

    async def test_event_dispatcher_initialization(self, connection_manager):
        """Test that EventDispatcher initializes correctly."""
        dispatcher = EventDispatcher(
            connection_manager=connection_manager,
            redis_url="redis://localhost:6379/0",
        )

        assert dispatcher._connection_manager == connection_manager
        assert dispatcher._redis_url == "redis://localhost:6379/0"
        assert dispatcher._running is False

    async def test_publish_event_to_redis(self, connection_manager):
        """Test publishing events to Redis."""
        dispatcher = EventDispatcher(
            connection_manager=connection_manager,
            redis_url="redis://localhost:6379/0",
        )

        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()
        dispatcher._redis_client = mock_redis

        # Publish event
        event = WebSocketEvent(
            type=EventType.SALE_CREATED,
            tenant_id="tenant1",
            payload={"sale_id": "123"},
        )
        await dispatcher.publish_event(event, tenant_id="tenant1")

        # Verify Redis publish was called
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "pos:events:tenant1"  # Channel
        assert "sale.created" in call_args[0][1]  # Event JSON

    async def test_publish_to_role_bypasses_redis(self, connection_manager):
        """Test that publish_to_role uses connection manager directly."""
        dispatcher = EventDispatcher(
            connection_manager=connection_manager,
            redis_url="redis://localhost:6379/0",
        )

        # Mock connection manager broadcast_to_role
        connection_manager.broadcast_to_role = AsyncMock()

        # Publish to role
        event = WebSocketEvent(
            type=EventType.INVENTORY_LOW_STOCK,
            tenant_id="tenant1",
            payload={"product_id": "456"},
        )
        await dispatcher.publish_to_role(event, tenant_id="tenant1", role="manager")

        # Verify connection manager was called directly
        connection_manager.broadcast_to_role.assert_called_once_with(
            tenant_id="tenant1",
            role="manager",
            event=event,
        )
