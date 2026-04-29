# Phase 12.1: Payment Integration Architecture - Complete

## Overview
Phase 12.1 establishes the foundational payment processing infrastructure for the POS system, including domain entities, repository patterns, provider abstractions, and Stripe integration.

## What Was Built

### 1. Domain Layer
**File**: `backend/app/domain/payments/entities.py`
- **Payment Entity**: Core aggregate with full payment lifecycle
  - Payment methods: cash, card, mobile, gift_card, bank_transfer, check
  - Payment statuses: pending, authorized, captured, completed, failed, cancelled, refunded, partially_refunded
  - Payment providers: internal (cash), stripe, paypal, square
  - State machine with validation: `authorize()`, `capture()`, `complete()`, `fail()`, `refund()`, `cancel()`
  - Optimistic locking with version field
  - Refund tracking (partial/full)
  - Card details (last4, brand)

- **Static Factories**:
  - `Payment.create_cash_payment()` - Immediate completion
  - `Payment.create_card_payment()` - Pending authorization

- **Value Objects**:
  - PaymentMethod enum
  - PaymentStatus enum
  - PaymentProvider enum

### 2. Application Layer
**File**: `backend/app/application/payments/ports.py`
- **IPaymentProvider Interface**:
  - `create_payment_intent()` - Initialize payment with provider
  - `capture_payment()` - Capture authorized funds
  - `refund_payment()` - Issue refund
  - `cancel_payment()` - Cancel pending payment
  - `get_payment_status()` - Check payment status

- **Request/Result DTOs**:
  - PaymentIntentRequest/Result
  - RefundRequest/Result
  - Support for client_secret (3D Secure), metadata, error messages

- **IPaymentRepository Interface**:
  - `add()`, `get_by_id()`, `get_by_sale_id()`, `update()`
  - `get_by_provider_transaction_id()` - Webhook support

**File**: `backend/app/application/payments/use_cases.py`
- **ProcessCashPayment**: Immediate cash payment completion
- **ProcessCardPayment**: Card payment with provider authorization
- **CapturePayment**: Capture authorized payment
- **RefundPayment**: Full/partial refund with provider integration
- **GetPaymentsBySale**: Retrieve payment history for sale

### 3. Infrastructure Layer
**File**: `backend/app/infrastructure/payments/stripe_provider.py`
- **StripePaymentProvider**: Full Stripe SDK integration
  - Payment intent creation with manual capture
  - Authorization and capture workflow
  - Refund processing (with reason tracking)
  - Payment cancellation
  - Status checking
  - Comprehensive error handling (CardError, StripeError)
  - Structured logging with trace context

**File**: `backend/app/infrastructure/db/models/payment_model.py`
- **PaymentModel**: SQLAlchemy ORM model
  - Maps 1:1 to Payment entity
  - Foreign key to sales table (cascade delete)
  - Indexes: sale_id, status, provider_transaction_id, created_at
  - Check constraints: amount > 0, refunded_amount validation
  - JSON field for provider_metadata

**File**: `backend/app/infrastructure/db/repositories/payment_repository.py`
- **PaymentRepository**: SQLAlchemy repository implementation
  - Async session management
  - Entity-to-model mapping
  - Joined loading for sale relationship

**Migration**: `alembic/versions/2a7bd182147b_create_payments_table.py`
- Creates payments table with all fields, constraints, indexes
- Foreign key to sales.id with CASCADE delete
- Check constraints for amount validation

### 4. API Layer
**File**: `backend/app/api/schemas/payment.py`
- **Request Schemas**:
  - ProcessCashPaymentRequest
  - ProcessCardPaymentRequest (with provider validation)
  - CapturePaymentRequest (supports partial capture)
  - RefundPaymentRequest
- **Response Schemas**:
  - PaymentResponse (base)
  - CardPaymentResponse (includes client_secret)
  - PaymentListResponse

**File**: `backend/app/api/routers/payments_router.py`
- **POST /api/v1/payments/cash**: Process cash payment
- **POST /api/v1/payments/card**: Initiate card payment (returns client_secret)
- **POST /api/v1/payments/capture**: Capture authorized payment
- **POST /api/v1/payments/refund**: Refund payment (full/partial)
- **GET /api/v1/payments/sale/{sale_id}**: Get payment history

### 5. Configuration
**Updated**: `backend/app/core/settings.py`
- Added Stripe configuration:
  - STRIPE_SECRET_KEY
  - STRIPE_PUBLISHABLE_KEY
  - STRIPE_WEBHOOK_SECRET
  - PAYMENT_CURRENCY (default: USD)

**Updated**: `backend/pyproject.toml`
- Added `stripe = "^7.0.0"` dependency

**Updated**: `backend/app/api/main.py`
- Registered payments_router

**Updated**: `backend/app/infrastructure/db/models/sale_model.py`
- Added payments relationship to SaleModel

### 6. Testing
**File**: `backend/tests/unit/domain/test_payment.py`
- 15 unit tests covering:
  - Payment creation (cash, card)
  - Authorization workflow
  - Capture and completion
  - Refunds (partial, full)
  - Failure and cancellation
  - Invalid state transitions
  - Version increment verification
  - Edge cases (negative amounts, excessive refunds)

## Architecture Decisions

### Payment Workflow
1. **Cash Payments**: Single-step completion (no provider)
2. **Card Payments**: Multi-step with provider
   - Create payment intent (PENDING)
   - Authorize (requires frontend confirmation with client_secret)
   - Capture (moves funds to merchant)
   - Complete (finalize)

### Provider Abstraction
- IPaymentProvider allows swapping Stripe for PayPal, Square, etc.
- Provider-agnostic domain layer
- Provider metadata stored as JSON for flexibility

### State Management
- Optimistic locking with version field prevents concurrent modifications
- Clear state machine with validation prevents invalid transitions
- Refunds tracked separately (supports partial refunds)

### Repository Pattern
- IPaymentRepository hides persistence details
- Easy to mock for testing
- Supports provider_transaction_id lookup for webhook processing

## Integration Points

### With Sales Domain
- Payments linked to sales via foreign key
- Sale-level payment aggregation (future: split payments)
- Payment events trigger sale status updates

### With WebSocket (Phase 11)
- Future: Broadcast payment status changes
- Real-time updates for payment authorization/capture

### With Celery (Phase 18)
- Future: Async receipt generation after payment
- Background refund processing
- Scheduled payment reconciliation

## Configuration Required

### Development (.env)
```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
PAYMENT_CURRENCY=USD
```

### Production
- Use live Stripe keys (sk_live_..., pk_live_...)
- Configure webhook endpoint in Stripe dashboard
- Set CORS_ORIGINS to include frontend domain

## API Usage Examples

### Process Cash Payment
```bash
POST /api/v1/payments/cash
{
  "sale_id": "01JC...",
  "amount": 50.00,
  "currency": "USD"
}
```

### Process Card Payment
```bash
POST /api/v1/payments/card
{
  "sale_id": "01JC...",
  "amount": 50.00,
  "currency": "USD",
  "provider": "stripe",
  "description": "POS Sale #12345"
}
# Returns client_secret for frontend confirmation
```

### Capture Payment
```bash
POST /api/v1/payments/capture
{
  "payment_id": "01JC...",
  "amount": 50.00  # Optional: partial capture
}
```

### Refund Payment
```bash
POST /api/v1/payments/refund
{
  "payment_id": "01JC...",
  "amount": 25.00,  # Partial refund
  "reason": "Customer requested"
}
```

## Database Schema

```sql
CREATE TABLE payments (
    id VARCHAR(26) PRIMARY KEY,
    sale_id VARCHAR(26) NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    method VARCHAR(50) NOT NULL,
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) NOT NULL,
    status VARCHAR(50) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    provider_transaction_id VARCHAR(255),
    provider_metadata JSON,
    card_last4 VARCHAR(4),
    card_brand VARCHAR(50),
    authorized_at TIMESTAMP WITH TIME ZONE,
    captured_at TIMESTAMP WITH TIME ZONE,
    refunded_amount NUMERIC(12,2) NOT NULL DEFAULT 0 
        CHECK (refunded_amount >= 0 AND refunded_amount <= amount),
    refunded_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(26) NOT NULL,
    notes TEXT,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX ix_payments_sale_id ON payments(sale_id);
CREATE INDEX ix_payments_status ON payments(status);
CREATE INDEX ix_payments_provider_transaction_id ON payments(provider_transaction_id);
CREATE INDEX ix_payments_created_at ON payments(created_at);
```

## Testing Strategy
- ✅ Unit tests: 15 tests for Payment entity
- ⏳ Integration tests: Payment repository (Phase 12.6)
- ⏳ Integration tests: API endpoints (Phase 12.6)
- ⏳ Integration tests: Stripe provider (Phase 12.6)

## Next Steps (Phase 12.2)

### Discount & Promotion Engine
1. Create Discount/Promotion domain entities
2. Implement discount calculation rules (percentage, fixed, BOGO)
3. Add coupon code validation
4. Create promotion repository
5. Build promotion management API
6. Integrate discounts with sales workflow

## Dependencies Installed
- `stripe==7.0.0` - Stripe Python SDK

## Files Created/Modified
**Created (14 files)**:
- `backend/app/domain/payments/entities.py`
- `backend/app/domain/payments/__init__.py`
- `backend/app/application/payments/ports.py`
- `backend/app/application/payments/use_cases.py`
- `backend/app/application/payments/__init__.py`
- `backend/app/infrastructure/payments/stripe_provider.py`
- `backend/app/infrastructure/payments/__init__.py`
- `backend/app/infrastructure/db/models/payment_model.py`
- `backend/app/infrastructure/db/repositories/payment_repository.py`
- `backend/app/api/schemas/payment.py`
- `backend/app/api/routers/payments_router.py`
- `backend/alembic/versions/2a7bd182147b_create_payments_table.py`
- `backend/tests/unit/domain/test_payment.py`
- `docs/phase12-1-complete.md` (this file)

**Modified (4 files)**:
- `backend/app/core/settings.py` - Added Stripe configuration
- `backend/app/api/main.py` - Registered payments router
- `backend/pyproject.toml` - Added stripe dependency
- `backend/app/infrastructure/db/models/sale_model.py` - Added payments relationship

## Compliance with Playbook
✅ **Domain-Driven**: Payment aggregate with clear boundaries  
✅ **Ports & Adapters**: IPaymentProvider abstraction, Stripe adapter  
✅ **Repository Pattern**: IPaymentRepository with SQLAlchemy implementation  
✅ **ULID Identifiers**: Payment IDs use `generate_ulid()`  
✅ **Money Value Object**: All amounts use `Money(Decimal, str)`  
✅ **Optimistic Locking**: Version field incremented on state changes  
✅ **Async/Await**: All repository methods async  
✅ **Structured Logging**: Stripe provider uses structlog with context  
✅ **Error Handling**: DomainError subclasses, ValidationError for invalid states  
✅ **Dependency Injection**: FastAPI Depends() for repositories and providers  

## Status
✅ **Phase 12.1 Complete** - Payment integration architecture fully implemented and ready for testing.

---

**Phase Progress**: 12.1 of 12.7 (14% of Phase 12)  
**Overall Progress**: 12 of 23 phases (52%)
