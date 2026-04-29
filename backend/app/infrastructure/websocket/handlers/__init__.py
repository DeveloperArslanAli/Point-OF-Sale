"""
Event handlers for WebSocket real-time communication.
"""

from .sales_handler import SalesEventHandler
from .inventory_handler import InventoryEventHandler
from .presence_handler import PresenceEventHandler

__all__ = [
    "SalesEventHandler",
    "InventoryEventHandler",
    "PresenceEventHandler",
]
