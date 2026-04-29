# Phase 11: Real-Time Communication Layer - Implementation Guide

**Duration:** 2 Sprints (15 days)  
**Priority:** 🔴 CRITICAL  
**Team:** 2 Engineers (1 Backend + 1 Frontend)  
**Prerequisites:** Phase 18 (Async Jobs) Complete

---

## 🎯 Objectives

Build real-time bidirectional communication for:
- ✅ Live dashboard updates (sales counter, active sessions)
- ✅ Inventory alerts (low stock warnings pushed to all terminals)
- ✅ Price changes broadcast instantly
- ✅ Multi-terminal cart synchronization
- ✅ Cashier presence system (who's online)
- ✅ Admin notifications (returns, voids, high-value sales)

---

## 🏗️ Architecture Decision

### WebSocket vs SSE vs Polling

| Method | Use Case | Chosen |
|--------|----------|--------|
| **WebSocket** | Bidirectional, low latency | ✅ Primary |
| **SSE** | Server→Client only | ✅ Fallback |
| **Polling** | Compatibility | ❌ Too chatty |

**Tech Stack:**
- Backend: FastAPI WebSocket + Redis Pub/Sub
- Frontend: Native WebSocket client in Flet
- Message Format: JSON events with type/payload

---

## ✅ Prerequisites

- [x] Phase 18 complete (Celery + Redis)
- [x] Redis running and accessible
- [x] `python-socketio` or native WebSocket support
- [x] Event schema designed

---

## 📂 File Structure

```
backend/
  app/
    infrastructure/
      websocket/
        __init__.py
        connection_manager.py      # WebSocket connection pool
        event_dispatcher.py        # Redis pub/sub → WebSocket
        events.py                  # Event types/schemas
        handlers/
          __init__.py
          sales_handler.py         # Handle sales events
          inventory_handler.py     # Handle inventory events
          presence_handler.py      # Handle user presence
    api/
      routers/
        websocket_router.py        # WebSocket endpoint
  tests/
    integration/
      websocket/
        test_connection_manager.py
        test_event_dispatcher.py

modern_client/
  services/
    websocket.py                   # WebSocket client service
  views/
    live_dashboard.py              # Real-time dashboard
```

---

## 🔧 Implementation Steps

### **Week 1: Backend WebSocket Infrastructure**

#### Day 1-2: Connection Manager

**File:** `backend/app/infrastructure/websocket/connection_manager.py`
```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, Optional
import structlog
import json

logger = structlog.get_logger()


class ConnectionManager:
    """
    Manages WebSocket connections with tenant/user/role awareness.
    
    Features:
    - Connection pooling by tenant
    - User authentication tracking
    - Role-based broadcasting
    - Heartbeat/keepalive
    """
    
    def __init__(self):
        # {tenant_id: {user_id: WebSocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        
        # {user_id: {tenant_id, role, connected_at}}
        self.user_metadata: Dict[str, dict] = {}
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        tenant_id: str,
        role: str,
    ):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = {}
        
        self.active_connections[tenant_id][user_id] = websocket
        self.user_metadata[user_id] = {
            "tenant_id": tenant_id,
            "role": role,
            "connected_at": datetime.now(UTC).isoformat(),
        }
        
        logger.info(
            "websocket_connected",
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
        )
        
        # Send welcome message
        await self.send_personal_message(
            user_id,
            {
                "type": "connection_established",
                "user_id": user_id,
                "server_time": datetime.now(UTC).isoformat(),
            },
        )
    
    def disconnect(self, user_id: str):
        """Remove a WebSocket connection."""
        if user_id in self.user_metadata:
            tenant_id = self.user_metadata[user_id]["tenant_id"]
            
            if tenant_id in self.active_connections:
                self.active_connections[tenant_id].pop(user_id, None)
                
                if not self.active_connections[tenant_id]:
                    del self.active_connections[tenant_id]
            
            del self.user_metadata[user_id]
            
            logger.info("websocket_disconnected", user_id=user_id)
    
    async def send_personal_message(self, user_id: str, message: dict):
        """Send message to a specific user."""
        if user_id in self.user_metadata:
            tenant_id = self.user_metadata[user_id]["tenant_id"]
            websocket = self.active_connections.get(tenant_id, {}).get(user_id)
            
            if websocket:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error("send_message_failed", user_id=user_id, error=str(e))
                    self.disconnect(user_id)
    
    async def broadcast_to_tenant(self, tenant_id: str, message: dict):
        """Broadcast message to all users in a tenant."""
        if tenant_id in self.active_connections:
            disconnected = []
            
            for user_id, websocket in self.active_connections[tenant_id].items():
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(
                        "broadcast_failed",
                        user_id=user_id,
                        error=str(e),
                    )
                    disconnected.append(user_id)
            
            for user_id in disconnected:
                self.disconnect(user_id)
    
    async def broadcast_to_role(
        self,
        tenant_id: str,
        role: str,
        message: dict,
    ):
        """Broadcast message to all users with a specific role."""
        if tenant_id in self.active_connections:
            for user_id, websocket in self.active_connections[tenant_id].items():
                user_role = self.user_metadata[user_id]["role"]
                
                if user_role == role:
                    try:
                        await websocket.send_json(message)
                    except Exception:
                        self.disconnect(user_id)
    
    def get_active_users(self, tenant_id: str) -> Set[str]:
        """Get set of active user IDs for a tenant."""
        return set(self.active_connections.get(tenant_id, {}).keys())
    
    def get_connection_count(self, tenant_id: Optional[str] = None) -> int:
        """Get total active connections (optionally filtered by tenant)."""
        if tenant_id:
            return len(self.active_connections.get(tenant_id, {}))
        return sum(len(conns) for conns in self.active_connections.values())


# Singleton instance
manager = ConnectionManager()
```

#### Day 3: Event Schema

**File:** `backend/app/infrastructure/websocket/events.py`
```python
from enum import Enum
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime


class EventType(str, Enum):
    """WebSocket event types."""
    
    # Connection lifecycle
    CONNECTION_ESTABLISHED = "connection_established"
    HEARTBEAT = "heartbeat"
    
    # Sales events
    SALE_CREATED = "sale_created"
    SALE_VOIDED = "sale_voided"
    HIGH_VALUE_SALE = "high_value_sale"
    
    # Inventory events
    INVENTORY_LOW = "inventory_low"
    INVENTORY_UPDATED = "inventory_updated"
    PRICE_CHANGED = "price_changed"
    
    # Product import events
    IMPORT_STARTED = "import_started"
    IMPORT_PROGRESS = "import_progress"
    IMPORT_COMPLETED = "import_completed"
    IMPORT_FAILED = "import_failed"
    
    # Presence events
    USER_ONLINE = "user_online"
    USER_OFFLINE = "user_offline"
    
    # Cart sync events
    CART_UPDATED = "cart_updated"
    
    # Admin alerts
    RETURN_CREATED = "return_created"
    LARGE_DISCOUNT_APPLIED = "large_discount_applied"


class WebSocketEvent(BaseModel):
    """Base WebSocket event structure."""
    
    type: EventType
    tenant_id: str
    timestamp: datetime
    payload: dict[str, Any]
    metadata: Optional[dict[str, Any]] = None


# Specific event payloads

class SaleCreatedPayload(BaseModel):
    sale_id: str
    total_amount: str
    currency: str
    cashier_id: str
    customer_id: Optional[str]


class InventoryLowPayload(BaseModel):
    product_id: str
    product_name: str
    current_quantity: int
    reorder_point: int


class PriceChangedPayload(BaseModel):
    product_id: str
    product_name: str
    old_price: str
    new_price: str
    currency: str


class ImportProgressPayload(BaseModel):
    job_id: str
    total_rows: int
    processed_rows: int
    error_count: int
    status: str


def create_event(
    event_type: EventType,
    tenant_id: str,
    payload: dict,
    metadata: Optional[dict] = None,
) -> dict:
    """Factory function to create WebSocket events."""
    return {
        "type": event_type.value,
        "tenant_id": tenant_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
        "metadata": metadata or {},
    }
```

#### Day 4-5: Redis Event Dispatcher

**File:** `backend/app/infrastructure/websocket/event_dispatcher.py`
```python
import redis.asyncio as redis
import json
import structlog
from app.core.settings import get_settings
from app.infrastructure.websocket.connection_manager import manager
from app.infrastructure.websocket.events import EventType

logger = structlog.get_logger()


class EventDispatcher:
    """
    Dispatches events from Redis Pub/Sub to WebSocket clients.
    
    Flow:
    1. Application publishes event to Redis channel
    2. EventDispatcher subscribes to channel
    3. Receives event and broadcasts to WebSocket clients
    """
    
    def __init__(self):
        settings = get_settings()
        self.redis_client = redis.from_url(settings.CELERY_BROKER_URL)
        self.pubsub = None
        self.running = False
    
    async def start(self):
        """Start listening to Redis pub/sub."""
        self.pubsub = self.redis_client.pubsub()
        
        # Subscribe to channels
        await self.pubsub.subscribe(
            "pos:events:sales",
            "pos:events:inventory",
            "pos:events:imports",
            "pos:events:presence",
            "pos:events:admin",
        )
        
        self.running = True
        logger.info("event_dispatcher_started")
        
        # Start consuming messages
        await self._consume_messages()
    
    async def stop(self):
        """Stop event dispatcher."""
        self.running = False
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        await self.redis_client.close()
        logger.info("event_dispatcher_stopped")
    
    async def _consume_messages(self):
        """Consume messages from Redis pub/sub."""
        while self.running:
            try:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                
                if message and message["type"] == "message":
                    await self._handle_message(message)
                    
            except Exception as e:
                logger.error("event_consume_error", error=str(e))
    
    async def _handle_message(self, message: dict):
        """Handle incoming Redis message."""
        try:
            event = json.loads(message["data"])
            event_type = EventType(event["type"])
            tenant_id = event["tenant_id"]
            
            logger.info(
                "event_received",
                type=event_type.value,
                tenant_id=tenant_id,
            )
            
            # Route to appropriate handler
            if event_type in [
                EventType.SALE_CREATED,
                EventType.HIGH_VALUE_SALE,
            ]:
                await self._broadcast_to_all(tenant_id, event)
                
            elif event_type == EventType.INVENTORY_LOW:
                # Send to managers and inventory staff
                await manager.broadcast_to_role(tenant_id, "MANAGER", event)
                await manager.broadcast_to_role(tenant_id, "INVENTORY", event)
                
            elif event_type in [
                EventType.PRICE_CHANGED,
                EventType.INVENTORY_UPDATED,
            ]:
                # Broadcast to all terminals
                await self._broadcast_to_all(tenant_id, event)
                
            elif event_type == EventType.RETURN_CREATED:
                # Alert managers only
                await manager.broadcast_to_role(tenant_id, "MANAGER", event)
                
            else:
                # Default: broadcast to tenant
                await self._broadcast_to_all(tenant_id, event)
                
        except Exception as e:
            logger.error("event_handle_error", error=str(e))
    
    async def _broadcast_to_all(self, tenant_id: str, event: dict):
        """Broadcast event to all users in tenant."""
        await manager.broadcast_to_tenant(tenant_id, event)
    
    async def publish_event(self, channel: str, event: dict):
        """Publish an event to Redis channel."""
        try:
            await self.redis_client.publish(
                channel,
                json.dumps(event),
            )
            logger.info("event_published", channel=channel, type=event["type"])
        except Exception as e:
            logger.error("event_publish_error", channel=channel, error=str(e))


# Global dispatcher instance
dispatcher = EventDispatcher()


# Helper functions for publishing events

async def publish_sale_event(sale_id: str, tenant_id: str, **kwargs):
    """Publish sale created event."""
    from app.infrastructure.websocket.events import create_event, EventType
    
    event = create_event(
        EventType.SALE_CREATED,
        tenant_id,
        {"sale_id": sale_id, **kwargs},
    )
    await dispatcher.publish_event("pos:events:sales", event)


async def publish_inventory_alert(product_id: str, tenant_id: str, **kwargs):
    """Publish low inventory alert."""
    from app.infrastructure.websocket.events import create_event, EventType
    
    event = create_event(
        EventType.INVENTORY_LOW,
        tenant_id,
        {"product_id": product_id, **kwargs},
    )
    await dispatcher.publish_event("pos:events:inventory", event)


async def publish_price_change(product_id: str, tenant_id: str, **kwargs):
    """Publish price change event."""
    from app.infrastructure.websocket.events import create_event, EventType
    
    event = create_event(
        EventType.PRICE_CHANGED,
        tenant_id,
        {"product_id": product_id, **kwargs},
    )
    await dispatcher.publish_event("pos:events:inventory", event)
```

#### Day 6: WebSocket Endpoint

**File:** `backend/app/api/routers/websocket_router.py`
```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from app.api.dependencies.auth import get_current_user
from app.infrastructure.websocket.connection_manager import manager
from app.infrastructure.websocket.event_dispatcher import dispatcher
import structlog

logger = structlog.get_logger()
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),  # JWT token from query param
):
    """
    WebSocket endpoint for real-time communication.
    
    Connection URL: ws://localhost:8000/api/v1/ws?token=<jwt_token>
    
    Events received by client:
    - connection_established
    - sale_created
    - inventory_low
    - price_changed
    - import_progress
    - etc.
    
    Client can send:
    - heartbeat (keepalive)
    - subscribe (to specific event types)
    - unsubscribe
    """
    
    # Authenticate user from token
    try:
        from app.infrastructure.auth.token_provider import TokenProvider
        from app.core.settings import get_settings
        
        settings = get_settings()
        provider = TokenProvider(settings.JWT_SECRET_KEY, settings.JWT_ISSUER)
        payload = provider.decode_token(token)
        
        user_id = payload.get("sub")
        role = payload.get("role")
        tenant_id = payload.get("tenant_id", "default")
        
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
            
    except Exception as e:
        logger.error("websocket_auth_failed", error=str(e))
        await websocket.close(code=4001, reason="Authentication failed")
        return
    
    # Connect user
    await manager.connect(websocket, user_id, tenant_id, role)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "heartbeat":
                # Respond to keepalive
                await websocket.send_json({
                    "type": "heartbeat_ack",
                    "timestamp": datetime.now(UTC).isoformat(),
                })
                
            elif message_type == "subscribe":
                # Client wants to subscribe to specific events
                event_types = data.get("event_types", [])
                logger.info("client_subscribed", user_id=user_id, events=event_types)
                # TODO: Implement selective subscription
                
            elif message_type == "ping":
                await websocket.send_json({"type": "pong"})
                
            else:
                logger.warning("unknown_message_type", type=message_type)
                
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        logger.info("websocket_client_disconnected", user_id=user_id)
        
    except Exception as e:
        logger.error("websocket_error", user_id=user_id, error=str(e))
        manager.disconnect(user_id)


@router.get("/ws/stats")
async def get_websocket_stats(
    current_user = Depends(get_current_user),
) -> dict:
    """Get WebSocket connection statistics."""
    tenant_id = getattr(current_user, "tenant_id", "default")
    
    return {
        "total_connections": manager.get_connection_count(),
        "tenant_connections": manager.get_connection_count(tenant_id),
        "active_users": list(manager.get_active_users(tenant_id)),
    }
```

#### Day 7: Integrate Events into Use Cases

**Example:** Update `RecordSaleUseCase` to publish event

**File:** `backend/app/application/sales/use_cases/record_sale.py`
```python
from app.infrastructure.websocket.event_dispatcher import publish_sale_event

class RecordSaleUseCase:
    async def execute(self, input_: RecordSaleInput) -> RecordSaleResult:
        # ... existing sale recording logic ...
        
        sale = Sale.create(...)
        await self.sales_repo.add(sale)
        
        # NEW: Publish real-time event
        await publish_sale_event(
            sale_id=sale.id,
            tenant_id=sale.tenant_id,
            total_amount=str(sale.total_amount.amount),
            currency=sale.currency,
            cashier_id=input_.cashier_id,
            customer_id=input_.customer_id,
        )
        
        return RecordSaleResult(sale=sale)
```

---

### **Week 2: Frontend Integration**

#### Day 8-9: WebSocket Client Service

**File:** `modern_client/services/websocket.py`
```python
import asyncio
import websocket
import json
import jwt as pyjwt
from typing import Callable, Dict
import structlog

logger = structlog.get_logger()


class WebSocketClient:
    """
    WebSocket client for real-time updates.
    
    Usage:
        ws_client = WebSocketClient("ws://localhost:8000/api/v1/ws", token)
        ws_client.on("sale_created", handle_sale_created)
        await ws_client.connect()
    """
    
    def __init__(self, url: str, token: str):
        self.url = f"{url}?token={token}"
        self.token = token
        self.ws = None
        self.running = False
        self.event_handlers: Dict[str, list[Callable]] = {}
        self.reconnect_delay = 5
    
    def on(self, event_type: str, handler: Callable):
        """Register event handler."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def connect(self):
        """Connect to WebSocket server."""
        self.running = True
        
        while self.running:
            try:
                self.ws = await websocket.connect(self.url)
                logger.info("websocket_connected", url=self.url)
                
                # Start receiving messages
                await self._receive_messages()
                
            except Exception as e:
                logger.error("websocket_connection_failed", error=str(e))
                await asyncio.sleep(self.reconnect_delay)
    
    async def _receive_messages(self):
        """Receive and handle messages."""
        while self.running:
            try:
                message = await self.ws.recv()
                event = json.loads(message)
                
                event_type = event.get("type")
                
                # Call registered handlers
                if event_type in self.event_handlers:
                    for handler in self.event_handlers[event_type]:
                        try:
                            handler(event)
                        except Exception as e:
                            logger.error(
                                "event_handler_error",
                                event_type=event_type,
                                error=str(e),
                            )
                            
            except websocket.exceptions.ConnectionClosed:
                logger.warning("websocket_connection_closed")
                break
                
            except Exception as e:
                logger.error("websocket_receive_error", error=str(e))
    
    async def send(self, data: dict):
        """Send message to server."""
        if self.ws:
            try:
                await self.ws.send(json.dumps(data))
            except Exception as e:
                logger.error("websocket_send_error", error=str(e))
    
    async def send_heartbeat(self):
        """Send heartbeat to keep connection alive."""
        while self.running:
            await self.send({"type": "heartbeat"})
            await asyncio.sleep(30)
    
    async def disconnect(self):
        """Disconnect from WebSocket server."""
        self.running = False
        if self.ws:
            await self.ws.close()
```

#### Day 10-12: Live Dashboard View

**File:** `modern_client/views/live_dashboard.py`
```python
import flet as ft
from datetime import datetime


class LiveDashboardView(ft.Container):
    """Real-time dashboard with WebSocket updates."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 20
        
        # Metrics
        self.sales_today = ft.Text("0", size=48, weight=ft.FontWeight.BOLD)
        self.revenue_today = ft.Text("$0.00", size=36)
        self.active_cashiers = ft.Text("0", size=24)
        self.low_stock_items = ft.Text("0", size=24, color="red")
        
        # Recent sales list
        self.recent_sales = ft.ListView(spacing=10, height=400)
        
        self.content = self._build_content()
        
        # Register WebSocket event handlers
        self.app.ws_client.on("sale_created", self._handle_sale_created)
        self.app.ws_client.on("inventory_low", self._handle_inventory_alert)
        self.app.ws_client.on("user_online", self._handle_user_online)
        self.app.ws_client.on("user_offline", self._handle_user_offline)
    
    def _build_content(self):
        return ft.Column([
            ft.Text("Live Dashboard", size=32, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            
            # Metrics row
            ft.Row([
                self._metric_card("Sales Today", self.sales_today, ft.icons.SHOPPING_CART),
                self._metric_card("Revenue Today", self.revenue_today, ft.icons.ATTACH_MONEY),
                self._metric_card("Active Cashiers", self.active_cashiers, ft.icons.PEOPLE),
                self._metric_card("Low Stock Alerts", self.low_stock_items, ft.icons.WARNING),
            ], spacing=20),
            
            ft.Divider(height=40),
            
            # Recent sales
            ft.Text("Recent Sales (Live)", size=20, weight=ft.FontWeight.BOLD),
            self.recent_sales,
        ], scroll=ft.ScrollMode.AUTO)
    
    def _metric_card(self, label, value_text, icon):
        return ft.Container(
            content=ft.Column([
                ft.Icon(icon, size=40, color=ft.colors.BLUE),
                value_text,
                ft.Text(label, size=14, color=ft.colors.GREY),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=10,
            padding=20,
            width=200,
        )
    
    def _handle_sale_created(self, event: dict):
        """Handle real-time sale creation."""
        payload = event["payload"]
        
        # Update metrics
        current_count = int(self.sales_today.value)
        self.sales_today.value = str(current_count + 1)
        
        current_revenue = float(self.revenue_today.value.replace("$", "").replace(",", ""))
        new_revenue = current_revenue + float(payload["total_amount"])
        self.revenue_today.value = f"${new_revenue:,.2f}"
        
        # Add to recent sales list
        sale_item = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.RECEIPT, color=ft.colors.GREEN),
                ft.Column([
                    ft.Text(f"Sale #{payload['sale_id'][:8]}", weight=ft.FontWeight.BOLD),
                    ft.Text(f"Amount: ${payload['total_amount']}", size=12),
                    ft.Text(f"Cashier: {payload['cashier_id'][:8]}", size=10, color=ft.colors.GREY),
                ]),
                ft.Text(datetime.now().strftime("%H:%M:%S"), size=12, color=ft.colors.GREY),
            ]),
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=5,
            padding=10,
        )
        
        # Add to top of list
        self.recent_sales.controls.insert(0, sale_item)
        
        # Keep only last 10
        if len(self.recent_sales.controls) > 10:
            self.recent_sales.controls.pop()
        
        # Update UI
        self.sales_today.update()
        self.revenue_today.update()
        self.recent_sales.update()
        
        # Show notification
        self.app.page.show_snack_bar(
            ft.SnackBar(
                content=ft.Text(f"New sale: ${payload['total_amount']}", color="white"),
                bgcolor=ft.colors.GREEN,
            )
        )
    
    def _handle_inventory_alert(self, event: dict):
        """Handle low inventory alert."""
        payload = event["payload"]
        
        # Update low stock counter
        current_count = int(self.low_stock_items.value)
        self.low_stock_items.value = str(current_count + 1)
        self.low_stock_items.update()
        
        # Show alert
        self.app.page.show_snack_bar(
            ft.SnackBar(
                content=ft.Text(
                    f"Low stock: {payload['product_name']} ({payload['current_quantity']} left)",
                    color="white",
                ),
                bgcolor=ft.colors.RED,
                duration=5000,
            )
        )
    
    def _handle_user_online(self, event: dict):
        """Handle user coming online."""
        current_count = int(self.active_cashiers.value)
        self.active_cashiers.value = str(current_count + 1)
        self.active_cashiers.update()
    
    def _handle_user_offline(self, event: dict):
        """Handle user going offline."""
        current_count = int(self.active_cashiers.value)
        self.active_cashiers.value = str(max(0, current_count - 1))
        self.active_cashiers.update()
```

#### Day 13: Integrate WebSocket into Main App

**File:** `modern_client/main.py`
```python
from services.websocket import WebSocketClient
import asyncio

class ModernPOSApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.setup_page()
        self.token = None
        self.user_role = None
        self.ws_client = None  # NEW
        self.navigate("login")
    
    def login(self, token):
        self.token = token
        # ... existing login logic ...
        
        # NEW: Connect to WebSocket
        self._connect_websocket()
        
        if self.user_role == "CASHIER":
            self.navigate("pos")
        else:
            self.navigate("dashboard")  # Use live_dashboard
    
    def _connect_websocket(self):
        """Connect to WebSocket server."""
        ws_url = "ws://localhost:8000/api/v1/ws"
        self.ws_client = WebSocketClient(ws_url, self.token)
        
        # Start connection in background
        asyncio.create_task(self.ws_client.connect())
        asyncio.create_task(self.ws_client.send_heartbeat())
```

---

### **Day 14-15: Testing & Optimization**

#### Integration Tests

**File:** `backend/tests/integration/websocket/test_websocket.py`
```python
import pytest
from fastapi.testclient import TestClient
from app.api.main import app


def test_websocket_connection_success(test_token):
    """Test WebSocket connection with valid token."""
    client = TestClient(app)
    
    with client.websocket_connect(f"/api/v1/ws?token={test_token}") as websocket:
        # Receive welcome message
        data = websocket.receive_json()
        assert data["type"] == "connection_established"
        
        # Send heartbeat
        websocket.send_json({"type": "heartbeat"})
        
        # Receive ack
        data = websocket.receive_json()
        assert data["type"] == "heartbeat_ack"


def test_websocket_connection_invalid_token():
    """Test WebSocket rejects invalid token."""
    client = TestClient(app)
    
    with pytest.raises(WebSocketException):
        with client.websocket_connect("/api/v1/ws?token=invalid"):
            pass


@pytest.mark.asyncio
async def test_broadcast_to_tenant(async_session, test_user):
    """Test broadcasting event to all users in tenant."""
    from app.infrastructure.websocket.event_dispatcher import publish_sale_event
    
    # TODO: Mock WebSocket connections
    await publish_sale_event(
        sale_id="01234",
        tenant_id=test_user.tenant_id,
        total_amount="50.00",
        currency="USD",
        cashier_id=test_user.id,
    )
    
    # Assert event was published to Redis
    # Assert connected clients received event
```

---

## 🧪 Testing Checklist

- [ ] WebSocket connection accepts valid JWT
- [ ] Connection rejects invalid/expired tokens
- [ ] Heartbeat keeps connection alive
- [ ] Events broadcast to correct tenant
- [ ] Role-based event filtering works
- [ ] Reconnection logic works after disconnect
- [ ] Multiple concurrent connections supported
- [ ] Connection count stats accurate
- [ ] Frontend receives and displays events
- [ ] Low inventory alerts show immediately

---

## 📊 Acceptance Criteria

✅ **Must Have:**
1. WebSocket connection established on login
2. Sale events appear on dashboard in <500ms
3. Inventory alerts pushed to managers
4. Connection survives network interruptions (auto-reconnect)
5. 100+ concurrent connections supported per tenant

✅ **Performance:**
- Message latency < 50ms (local)
- Message latency < 200ms (cloud)
- Connection overhead < 10MB/hour idle
- Broadcast to 50 clients < 100ms

✅ **Reliability:**
- Auto-reconnect after disconnect
- Message queue survives brief disconnects
- Graceful degradation if Redis unavailable

---

## 🔄 Event Flow Example

```
1. Cashier completes sale
   ↓
2. RecordSaleUseCase publishes event to Redis
   ↓
3. EventDispatcher receives from Redis
   ↓
4. Broadcasts to WebSocket clients (ConnectionManager)
   ↓
5. All dashboards update instantly
   ↓
6. Manager sees sale notification in <500ms
```

---

## 📝 Next Steps

After Phase 11 completion:
- ✅ Enhance **Phase 12** with real-time price updates
- ✅ Build **Phase 14** with live report progress
- ✅ Add **Phase 15** customer engagement notifications

---

**Status:** Ready for implementation  
**Blockers:** Phase 18 must be complete  
**Dependencies:** Redis Pub/Sub operational
