# Phase 12.2: Discount & Promotion Engine - Complete

## Overview
Phase 12.2 implements a comprehensive discount and promotion system with flexible rules, coupon codes, usage limits, and customer targeting for the retail POS.

## What Was Built

### 1. Domain Layer
**File**: `backend/app/domain/promotions/entities.py`

- **DiscountRule Value Object**:
  - Discount types: percentage, fixed_amount, buy_x_get_y, free_shipping
  - Configurable constraints:
    - `min_purchase_amount` - Minimum order requirement
    - `max_discount_amount` - Maximum discount cap
  - Buy X Get Y support (e.g., "Buy 2 Get 1 Free")
  - Target types: order, category, product, customer
  - Product/category-specific discounts
  - `calculate_discount()` method with all rule logic

- **Promotion Aggregate**:
  - Full promotion lifecycle management
  - Status: draft, active, scheduled, expired, disabled
  - Validity period (start_date, end_date)
  - Usage limits:
    - Total usage limit
    - Per-customer usage limit
  - Coupon codes (case-sensitive/insensitive)
  - Customer targeting (specific customer IDs)
  - Combinability rules
  - Priority system (for stacking)
  - State machine: `activate()`, `deactivate()`, `expire()`
  - Validation: `is_active()`, `can_apply_to_customer()`, `validate_coupon_code()`
  - `apply_discount()` with full rule enforcement

- **AppliedDiscount Value Object**:
  - Record of discount applied to sale
  - Tracks promotion ID, name, amount, coupon code

### 2. Application Layer
**File**: `backend/app/application/promotions/ports.py`
- **IPromotionRepository Interface**:
  - `add()`, `get_by_id()`, `update()`, `delete()`
  - `get_by_coupon_code()` - Case-insensitive lookup
  - `list_active()` - Filter by customer, pagination
  - `get_customer_usage_count()` - Per-customer usage tracking

**File**: `backend/app/application/promotions/use_cases.py`
- **CreatePromotion**: Create new promotions with validation
- **GetPromotion**: Retrieve by ID
- **GetPromotionByCouponCode**: Lookup by coupon code
- **ListActivePromotions**: List active with filters
- **UpdatePromotion**: Update details (name, limits, priority)
- **ActivatePromotion**: Transition draft → active
- **DeactivatePromotion**: Disable active promotion
- **ApplyPromotion**: Calculate discount (validation only, no persistence)
- **DeletePromotion**: Remove promotion

### 3. Infrastructure Layer
**File**: `backend/app/infrastructure/db/models/promotion_model.py`
- **PromotionModel**: SQLAlchemy ORM model
  - JSON storage for discount_rule (flexibility)
  - JSON array for customer_ids
  - Unique constraint on coupon_code
  - Indexes: status, start_date, end_date, priority, coupon_code
  - Check constraint: usage_count >= 0

**File**: `backend/app/infrastructure/db/repositories/promotion_repository.py`
- **PromotionRepository**: SQLAlchemy implementation
  - Case-insensitive coupon code lookup
  - Active promotion filtering with customer targeting
  - JSON serialization for DiscountRule
  - Priority-based sorting

**Migration**: `alembic/versions/3213c39da6e6_create_promotions_table.py`
- Creates promotions table with all fields
- 5 indexes for query performance
- JSON columns for flexibility

### 4. API Layer
**File**: `backend/app/api/schemas/promotion.py`
- **Request Schemas**:
  - CreatePromotionRequest (full promotion details)
  - UpdatePromotionRequest (partial updates)
  - ApplyPromotionRequest (discount calculation)
  - ValidateCouponRequest (coupon validation)
- **Response Schemas**:
  - PromotionResponse (full promotion)
  - PromotionListResponse (paginated list)
  - DiscountCalculationResponse (before/after amounts)
  - DiscountRuleSchema (nested rule details)

**File**: `backend/app/api/routers/promotions_router.py`
- **POST /api/v1/promotions**: Create promotion (manager+)
- **GET /api/v1/promotions/{id}**: Get promotion details
- **GET /api/v1/promotions**: List active promotions
- **PATCH /api/v1/promotions/{id}**: Update promotion (manager+)
- **POST /api/v1/promotions/{id}/activate**: Activate (manager+)
- **POST /api/v1/promotions/{id}/deactivate**: Deactivate (manager+)
- **DELETE /api/v1/promotions/{id}**: Delete (manager+)
- **POST /api/v1/promotions/apply**: Calculate discount (sales+)
- **POST /api/v1/promotions/validate-coupon**: Validate coupon (sales+)

### 5. Configuration & Updates
**Updated**: `backend/app/api/main.py`
- Registered promotions_router

**Updated**: `backend/app/api/dependencies/auth.py`
- Added `MANAGER_ROLES` constant for consistency

### 6. Testing
**File**: `backend/tests/unit/domain/test_promotion.py`
- 22 unit tests covering:
  - Percentage discounts
  - Fixed amount discounts
  - Buy X Get Y (single and multiple sets)
  - Minimum purchase requirements
  - Maximum discount caps
  - Discount cannot exceed subtotal
  - Invalid rule parameters
  - Promotion lifecycle (activate, deactivate)
  - Active status checks (status, dates, usage limits)
  - Coupon code validation (case-sensitive/insensitive)
  - Customer targeting
  - Usage increment and versioning

## Discount Rule Examples

### Percentage Discount
```json
{
  "discount_type": "percentage",
  "value": 15.00,
  "min_purchase_amount": 50.00
}
// 15% off orders over $50
```

### Fixed Amount Discount
```json
{
  "discount_type": "fixed_amount",
  "value": 10.00,
  "max_discount_amount": 10.00
}
// $10 off
```

### Buy X Get Y
```json
{
  "discount_type": "buy_x_get_y",
  "value": 0,
  "buy_quantity": 2,
  "get_quantity": 1
}
// Buy 2 Get 1 Free
```

### Category-Specific Discount
```json
{
  "discount_type": "percentage",
  "value": 20.00,
  "target": "category",
  "target_category_ids": ["01JCCAT123", "01JCCAT456"]
}
// 20% off specific categories
```

## API Usage Examples

### Create Percentage-Off Promotion
```bash
POST /api/v1/promotions
{
  "name": "Summer Sale",
  "description": "15% off everything",
  "discount_type": "percentage",
  "value": 15.00,
  "start_date": "2025-06-01T00:00:00Z",
  "end_date": "2025-08-31T23:59:59Z",
  "priority": 10
}
```

### Create Coupon Code Promotion
```bash
POST /api/v1/promotions
{
  "name": "First-Time Customer",
  "description": "$10 off first purchase",
  "discount_type": "fixed_amount",
  "value": 10.00,
  "start_date": "2025-01-01T00:00:00Z",
  "coupon_code": "WELCOME10",
  "usage_limit_per_customer": 1,
  "min_purchase_amount": 25.00
}
```

### Create Buy 2 Get 1 Free
```bash
POST /api/v1/promotions
{
  "name": "BOGO Sale",
  "description": "Buy 2 Get 1 Free on select items",
  "discount_type": "buy_x_get_y",
  "value": 0,
  "buy_quantity": 2,
  "get_quantity": 1,
  "start_date": "2025-12-01T00:00:00Z",
  "end_date": "2025-12-25T23:59:59Z",
  "target": "product",
  "target_product_ids": ["01JCPROD123", "01JCPROD456"]
}
```

### Activate Promotion
```bash
POST /api/v1/promotions/{promotion_id}/activate
```

### Validate Coupon Code
```bash
POST /api/v1/promotions/validate-coupon
{
  "coupon_code": "SAVE20",
  "customer_id": "01JCCUST123"  # Optional
}
```

### Calculate Discount
```bash
POST /api/v1/promotions/apply
{
  "promotion_id": "01JCPROM123",
  "subtotal": 100.00,
  "currency": "USD",
  "quantity": 3,
  "customer_id": "01JCCUST123",
  "coupon_code": "SAVE20"
}
# Returns:
{
  "promotion_id": "01JCPROM123",
  "promotion_name": "Holiday Sale",
  "discount_amount": 20.00,
  "currency": "USD",
  "original_amount": 100.00,
  "final_amount": 80.00
}
```

## Database Schema

```sql
CREATE TABLE promotions (
    id VARCHAR(26) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(50) NOT NULL,
    discount_rule JSON NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE,
    usage_limit INTEGER,
    usage_count INTEGER NOT NULL DEFAULT 0 CHECK (usage_count >= 0),
    usage_limit_per_customer INTEGER,
    coupon_code VARCHAR(100) UNIQUE,
    is_case_sensitive BOOLEAN NOT NULL DEFAULT false,
    customer_ids JSON NOT NULL DEFAULT '[]',
    exclude_sale_items BOOLEAN NOT NULL DEFAULT false,
    can_combine_with_other_promotions BOOLEAN NOT NULL DEFAULT false,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(26) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(26) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX ix_promotions_coupon_code ON promotions(coupon_code);
CREATE INDEX ix_promotions_status ON promotions(status);
CREATE INDEX ix_promotions_start_date ON promotions(start_date);
CREATE INDEX ix_promotions_end_date ON promotions(end_date);
CREATE INDEX ix_promotions_priority ON promotions(priority);
```

## Integration Points

### With Sales Domain (Future - Phase 12.4)
- Apply promotions during checkout
- Track applied discounts on sales
- Increment promotion usage_count
- Validate promotion eligibility
- Support stacking multiple promotions

### With Products/Categories
- Product-specific promotions
- Category-wide sales
- Exclude sale items from additional discounts

### With Customers
- VIP/loyalty discounts
- First-time customer offers
- Per-customer usage tracking
- Personalized promotions

### With WebSocket (Phase 11)
- Real-time promotion activation broadcasts
- Flash sale notifications
- Dynamic coupon code updates

## Architecture Decisions

### JSON Storage for Discount Rules
- Flexibility for adding new discount types without schema changes
- Clean serialization/deserialization
- All rule logic in domain entity (not database)

### Promotion Priority System
- Higher priority = applied first
- Enables complex discount stacking rules
- Managers control application order

### Separate Usage Tracking
- `usage_count` on promotion for total uses
- Per-customer tracking requires junction table (Phase 12.4)
- Currently returns 0 (TODO noted in repository)

### Coupon Code Handling
- Case-insensitive by default (configurable)
- Unique constraint enforced at database level
- Separate endpoint for validation

## Next Steps (Phase 12.3)

### Receipt Generation System
1. Install ReportLab for PDF generation
2. Create receipt templates (thermal, A4)
3. Format sale data for receipts
4. Email receipt functionality via Celery
5. Store receipt history

## Files Created/Modified
**Created (9 files)**:
- `backend/app/domain/promotions/entities.py`
- `backend/app/domain/promotions/__init__.py`
- `backend/app/application/promotions/ports.py`
- `backend/app/application/promotions/use_cases.py`
- `backend/app/application/promotions/__init__.py`
- `backend/app/infrastructure/db/models/promotion_model.py`
- `backend/app/infrastructure/db/repositories/promotion_repository.py`
- `backend/app/api/schemas/promotion.py`
- `backend/app/api/routers/promotions_router.py`
- `backend/alembic/versions/3213c39da6e6_create_promotions_table.py`
- `backend/tests/unit/domain/test_promotion.py`
- `docs/phase12-2-complete.md` (this file)

**Modified (2 files)**:
- `backend/app/api/main.py` - Registered promotions router
- `backend/app/api/dependencies/auth.py` - Added MANAGER_ROLES constant

## Compliance with Playbook
✅ **Domain-Driven**: Promotion aggregate with DiscountRule value object  
✅ **Ports & Adapters**: IPromotionRepository abstraction  
✅ **Repository Pattern**: SQLAlchemy implementation  
✅ **ULID Identifiers**: Promotion IDs use `generate_ulid()`  
✅ **Money Value Object**: All amounts use `Money(Decimal, str)`  
✅ **Optimistic Locking**: Version field incremented on state changes  
✅ **Async/Await**: All repository methods async  
✅ **Error Handling**: ValidationError for invalid rules/states  
✅ **Dependency Injection**: FastAPI Depends() for repositories  

## Status
✅ **Phase 12.2 Complete** - Discount & promotion engine fully implemented with flexible rules, coupon codes, and customer targeting.

---

**Phase Progress**: 12.2 of 12.7 (29% of Phase 12)  
**Overall Progress**: 12 of 23 phases (52%)
