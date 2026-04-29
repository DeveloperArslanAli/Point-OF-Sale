"""
WebSocket infrastructure for real-time communication.

Provides connection management, event dispatching, and Redis pub/sub integration.
"""

from .connection_manager import ConnectionManager
from .event_dispatcher import EventDispatcher
from .events import (
    EventType,
    WebSocketEvent,
    SalesEvent,
    InventoryEvent,
    PresenceEvent,
    PriceChangeEvent,
)

__all__ = [
    "ConnectionManager",
    "EventDispatcher",
    "EventType",
    "WebSocketEvent",
    "SalesEvent",
    "InventoryEvent",
    "PresenceEvent",
    "PriceChangeEvent",
]
