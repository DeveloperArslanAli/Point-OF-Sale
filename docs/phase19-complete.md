# Phase 19 Complete: API & Integration Layer

## Overview

Phase 19 implements a comprehensive API and integration layer enabling external systems to interact with the Retail POS platform via API keys and receive real-time notifications via webhooks.

## Implementation Summary

### ✅ API Key System (Complete)

**Domain Layer** ([entities.py](app/domain/api_keys/entities.py))
- `ApiKey` entity with ULID IDs, scopes, rate limiting, expiration
- 11 permission scopes: `read/write:products`, `read/write:inventory`, `read/write:sales`, `read/write:customers`, `read:reports`, `webhooks`, `full_access`
- Status lifecycle: `active` → `revoked` / `expired`

**Application Layer** ([use_cases/](app/application/api_keys/use_cases/))
- `CreateApiKeyUseCase` - Create new API key with scope validation and tenant limits
- `RevokeApiKeyUseCase` - Soft-delete with audit trail
- `GetApiKeyUseCase` - Single key retrieval
- `ListApiKeysUseCase` - Paginated listing with optional revoked filter
- `DeleteApiKeyUseCase` - Hard delete

**Infrastructure Layer** ([api_key_repository.py](app/infrastructure/db/repositories/api_key_repository.py))
- `SqlAlchemyApiKeyRepository` implementing the `ApiKeyRepository` protocol
- Optimistic locking with version control
- Multi-tenant isolation via tenant context

**API Layer** ([api_keys_router.py](app/api/routers/api_keys_router.py))
- 6 endpoints: Create, Get, List, Revoke, Delete, Regenerate
- Admin-only access control
- Full OpenAPI documentation

### ✅ Webhook System (Complete)

**Domain Layer** ([webhooks/entities.py](app/domain/webhooks/entities.py))
- `WebhookSubscription` - URL, secret, event filters, retry config
- `WebhookEvent` - Event type, payload, reference tracking
- `WebhookDelivery` - Delivery attempts with status, retry scheduling
- 24 event types covering sales, inventory, customers, products, returns, employees, loyalty, gift cards

**Application Layer** ([webhooks/ports.py](app/application/webhooks/ports.py))
- Repository protocols for subscriptions, events, deliveries
- Clean architecture separation

**Infrastructure Layer**

*Repositories* ([webhook_repository.py](app/infrastructure/db/repositories/webhook_repository.py))
- `SqlAlchemyWebhookSubscriptionRepository`
- `SqlAlchemyWebhookEventRepository` 
- `SqlAlchemyWebhookDeliveryRepository`
- `SqlAlchemyWebhookRepository` - Unified facade for Celery tasks

*Celery Tasks* ([webhook_tasks.py](app/infrastructure/tasks/webhook_tasks.py))
- `dispatch_webhook_event` - Async delivery with httpx
- `retry_failed_webhooks` - Scheduled retry processing
- `cleanup_old_webhook_deliveries` - Retention cleanup

*Event Publisher* ([event_publisher.py](app/infrastructure/webhooks/event_publisher.py))
- `WebhookEventPublisher` - Bridges domain events to webhook dispatch
- `publish_domain_events()` - Convenience function for use cases
- Maps 24 domain event types to webhook event types

**Celery Configuration** ([celery_app.py](app/infrastructure/tasks/celery_app.py))
- Added `webhooks` queue
- Scheduled tasks:
  - `retry-failed-webhooks-every-5min` - Every 5 minutes
  - `cleanup-old-webhook-deliveries-daily` - 3 AM daily

### ✅ Rate Limiting (Complete)

**Infrastructure** ([rate_limiter.py](app/infrastructure/rate_limiter.py))
- Redis-backed sliding window algorithm
- Route-specific configuration
- Graceful degradation when Redis unavailable

**API Middleware** ([rate_limiting.py](app/api/dependencies/rate_limiting.py))
- Configurable limits per endpoint
- Returns `429 Too Many Requests` with `Retry-After` header
- API key rate limits override defaults

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Systems                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
│  ┌─────────────┐   ┌─────────────────┐   ┌──────────────────┐  │
│  │  API Keys   │   │  Rate Limiting  │   │ Webhook Router   │  │
│  │   Router    │   │   Middleware    │   │ (Subscriptions)  │  │
│  └─────────────┘   └─────────────────┘   └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Application Layer                            │
│  ┌─────────────────┐              ┌─────────────────────────┐   │
│  │  API Key Use    │              │   Webhook Use Cases     │   │
│  │     Cases       │              │   (CRUD Subscriptions)  │   │
│  └─────────────────┘              └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                           │
│  ┌────────────────────────┐   ┌─────────────────────────────┐   │
│  │   Webhook Publisher    │   │      Celery Tasks           │   │
│  │  (Domain Event Bridge) │──▶│  ┌─────────────────────┐    │   │
│  └────────────────────────┘   │  │ dispatch_webhook    │    │   │
│                               │  │ retry_failed        │    │   │
│  ┌────────────────────────┐   │  │ cleanup_deliveries  │    │   │
│  │    Redis Rate Limiter  │   │  └─────────────────────┘    │   │
│  └────────────────────────┘   └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data Layer                                │
│  ┌─────────────────────┐   ┌────────────────────────────────┐   │
│  │  api_keys table     │   │  webhook_subscriptions table   │   │
│  │                     │   │  webhook_events table          │   │
│  │                     │   │  webhook_deliveries table      │   │
│  └─────────────────────┘   └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Usage Examples

### Publishing Domain Events as Webhooks

```python
from app.infrastructure.webhooks import publish_domain_events

class CompleteSaleUseCase:
    async def execute(self, sale_id: str) -> Sale:
        sale = await self._repo.get_by_id(sale_id)
        sale.complete()
        await self._repo.update(sale)
        
        # Publish domain events as webhooks
        events = sale.pull_events()
        publish_domain_events(events, tenant_id=self._tenant_id)
        
        return sale
```

### Creating an API Key

```python
from app.application.api_keys.use_cases import (
    CreateApiKeyUseCase,
    CreateApiKeyCommand,
)

command = CreateApiKeyCommand(
    name="POS Integration",
    scopes=["read:products", "write:inventory"],
    rate_limit_per_minute=120,
    created_by=current_user.id,
    tenant_id=tenant_id,
)

result = await use_case.execute(command)
print(f"API Key (save this!): {result.raw_key}")
```

## Event Types

| Category   | Events                                          |
|------------|------------------------------------------------|
| Sales      | sale.created, sale.completed, sale.voided      |
| Inventory  | inventory.low, inventory.updated, inventory.received |
| Customers  | customer.created, customer.updated, customer.deactivated |
| Products   | product.created, product.updated, product.deleted |
| Returns    | return.created, return.approved, return.completed |
| Employees  | employee.clock_in, employee.clock_out          |
| Loyalty    | loyalty.points_earned, loyalty.tier_changed    |
| Gift Cards | gift_card.created, gift_card.redeemed          |
| Orders     | order.created, order.shipped, order.delivered  |

## Remaining Items (Nice-to-Have)

These are optional enhancements not required for Phase 19 core completion:

- [ ] GraphQL endpoint (alternative to REST)
- [ ] Third-party integrations (Shopify, WooCommerce connectors)
- [ ] Developer documentation portal
- [ ] API versioning strategy (v2 endpoint prefix)
- [ ] API key usage analytics dashboard

## Testing

```bash
# Run Phase 19 specific tests
pytest tests/integration/api/test_api_keys.py -v
pytest tests/integration/api/test_webhooks.py -v
pytest tests/unit/api_keys/ -v
```

## Files Created/Modified

### New Files
- `app/infrastructure/tasks/webhook_tasks.py` - Celery webhook dispatch tasks
- `app/infrastructure/webhooks/__init__.py` - Webhook infrastructure package
- `app/infrastructure/webhooks/event_publisher.py` - Domain event bridge
- `app/application/api_keys/__init__.py` - API keys application layer
- `app/application/api_keys/ports.py` - Repository protocol
- `app/application/api_keys/use_cases/__init__.py` - Use cases package
- `app/application/api_keys/use_cases/create_api_key.py`
- `app/application/api_keys/use_cases/revoke_api_key.py`
- `app/application/api_keys/use_cases/get_api_key.py`
- `app/application/api_keys/use_cases/list_api_keys.py`
- `app/application/api_keys/use_cases/delete_api_key.py`

### Modified Files
- `app/infrastructure/tasks/celery_app.py` - Added webhooks queue and scheduled tasks
- `app/infrastructure/db/repositories/webhook_repository.py` - Added unified repository
- `app/infrastructure/db/repositories/api_key_repository.py` - Added missing protocol methods

---

**Phase 19 Status: ✅ COMPLETE (Core Functionality)**

*Date: 2024*
