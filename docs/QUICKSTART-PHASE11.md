# Phase 11 Real-Time Communication - Quick Start Guide

## Overview
Phase 11 adds WebSocket-based real-time communication to the POS system, enabling live updates for sales, inventory, prices, and user presence across all connected terminals.

## Quick Start

### 1. Start the Backend
```bash
cd backend
py -m poetry run uvicorn app.api.main:app --reload
```

The EventDispatcher will automatically start and connect to Redis on startup.

### 2. Connect a WebSocket Client

#### JavaScript Example
```javascript
const token = "your-jwt-token-from-login";
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws?token=${token}`);

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(`Event: ${data.type}`, data.payload);
    
    // Handle specific events
    switch(data.type) {
        case 'sale.created':
            console.log(`New sale: $${data.payload.total_amount}`);
            break;
        case 'inventory.low_stock':
            console.log(`⚠️ Low stock: ${data.payload.product_name}`);
            break;
        case 'price.changed':
            console.log(`Price updated: ${data.payload.product_name}`);
            break;
    }
};
```

### 3. Available Event Types

**Sales Events:**
- `sale.created` - New sale initiated
- `sale.completed` - Sale finalized  
- `sale.voided` - Sale cancelled

**Inventory Events:**
- `inventory.low_stock` - Stock below threshold
- `inventory.out_of_stock` - Item unavailable
- `inventory.updated` - Stock quantity changed

**Price Events:**
- `price.changed` - Product price updated

**Presence Events:**
- `presence.connected` - User came online
- `presence.disconnected` - User went offline

**Import Events:**
- `import.started` / `import.completed` / `import.failed`

## Monitoring

### Check Connection Stats
```bash
curl http://localhost:8000/api/v1/ws/stats
```

### List Connected Users
```bash
curl http://localhost:8000/api/v1/ws/connected-users?tenant_id=default
```

## Testing

Run WebSocket tests:
```bash
cd backend
py -m poetry run pytest tests/integration/websocket/ -v
```

Verify implementation:
```bash
cd backend
py -m poetry run python scripts/verify_phase11.py
```

## Architecture

```
API Endpoint → Event Handler → EventDispatcher → Redis Pub/Sub
                                       ↓
                              ConnectionManager → WebSocket Clients
```

## Features

✅ **Tenant Isolation** - Events only broadcast within tenant boundaries  
✅ **Role-Based Filtering** - Target specific roles (admin, manager, cashier)  
✅ **Multi-Instance Support** - Redis pub/sub enables clustering  
✅ **JWT Authentication** - Secure WebSocket connections  
✅ **Connection Pooling** - Efficient resource management  
✅ **Graceful Degradation** - Events don't block API responses  

## Next Steps

- **Phase 12:** Payment integrations with live payment status updates
- **Phase 14:** Advanced reporting with real-time dashboard updates
- **Phase 13:** Customer loyalty with live points updates

## Documentation

- Full implementation: `docs/phase11-complete.md`
- Original plan: `docs/phase11-realtime.md`
- Source code: `backend/app/infrastructure/websocket/`
- Tests: `backend/tests/integration/websocket/`

---

**Phase 11 Complete! 🎉**  
Real-time communication is now live across the entire POS system.
