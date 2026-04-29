# Phase 12.3: Receipt Generation System - Complete

## Overview
Phase 12.3 implements a comprehensive receipt generation system with PDF output in thermal (80mm) and A4 formats, email delivery via Celery, and receipt history tracking.

## What Was Built

### 1. Domain Layer
**File**: `backend/app/domain/receipts/entities.py`

- **ReceiptLineItem Value Object**:
  - Product details (name, SKU, quantity, unit price)
  - Line total and discount tracking
  - Validation: positive quantity, non-negative prices

- **ReceiptPayment Value Object**:
  - Payment method tracking (cash, card, gift_card, etc.)
  - Amount and reference number
  - Card last 4 digits (for card payments)

- **ReceiptTotals Value Object**:
  - Subtotal, tax, discount, total amounts
  - Amount paid and change given
  - Validation: all amounts non-negative

- **Receipt Aggregate**:
  - Store information (name, address, phone, tax ID)
  - Cashier and customer details
  - Line items, payments, totals collections
  - Sale date and tax rate
  - Optional notes and footer message
  - Format type (thermal or a4)
  - Locale support (default: en_US)
  - Helper methods:
    - `calculate_total_quantity()` - Sum all line item quantities
    - `get_primary_payment_method()` - Get largest payment method

### 2. Application Layer
**File**: `backend/app/application/receipts/ports.py`
- **IReceiptRepository Interface**:
  - `add()`, `get_by_id()`, `update()`
  - `get_by_sale_id()` - Lookup by sale
  - `get_by_receipt_number()` - Lookup by receipt number
  - `list_by_date_range()` - Date range queries with pagination

**File**: `backend/app/application/receipts/use_cases.py`
- **CreateReceipt**: Create and persist receipts
- **GetReceipt**: Retrieve by ID
- **GetReceiptBySaleId**: Retrieve by sale ID
- **GetReceiptByNumber**: Retrieve by receipt number
- **ListReceiptsByDateRange**: List receipts in date range

### 3. Infrastructure Layer - PDF Generation
**File**: `backend/app/infrastructure/services/receipt_pdf_generator.py`
- **ReceiptPDFGenerator Service**:
  - Thermal format (80mm width):
    - Compact layout for thermal printers
    - Center-aligned store header
    - Condensed line items
    - Small fonts (7-8pt)
    - Dynamic height calculation
  - A4 format:
    - Professional layout
    - Table-style line items
    - Larger fonts (9-12pt)
    - Two-column header info
  - ReportLab Canvas drawing
  - Returns PDF as bytes

**Features**:
- Store header with logo space
- Receipt metadata (number, date, cashier)
- Line items with quantities and prices
- Discounts clearly displayed
- Totals section (subtotal, tax, discount, total)
- Multiple payments supported
- Change given calculation
- Custom notes and footer messages

### 4. Infrastructure Layer - Persistence
**File**: `backend/app/infrastructure/db/models/receipt_model.py`
- **ReceiptModel**: SQLAlchemy ORM model
  - JSON columns: line_items, payments, totals
  - Indexed: sale_id (unique), receipt_number (unique), sale_date
  - Server defaults for format_type, locale, created_at

**File**: `backend/app/infrastructure/db/repositories/receipt_repository.py`
- **ReceiptRepository**: SQLAlchemy implementation
  - JSON serialization/deserialization for complex objects
  - Decimal → string conversion for JSON storage
  - Date range queries with ordering

**Migration**: `alembic/versions/e8d28c25aa2b_create_receipts_table.py`
- Creates receipts table (21 columns)
- 3 indexes for query performance
- JSON storage for flexible data structures

### 5. Infrastructure Layer - Email
**File**: `backend/app/infrastructure/tasks/email_tasks.py`
- **send_receipt_email Celery Task**:
  - Accepts PDF content as bytes
  - Formats professional HTML email
  - Attaches PDF receipt
  - Includes store branding
  - Async execution via Celery
  - Retry on failure (3 attempts)

**Email Template**:
- Store header with branding
- Thank you message
- Receipt number reference
- PDF attachment
- Contact information

### 6. API Layer
**File**: `backend/app/api/schemas/receipt.py`
- **Request Schemas**:
  - CreateReceiptRequest (full receipt data)
  - Nested: ReceiptLineItemSchema, ReceiptPaymentSchema, ReceiptTotalsSchema, MoneySchema
- **Response Schemas**:
  - ReceiptResponse (complete receipt)
  - ReceiptListResponse (paginated list)

**File**: `backend/app/api/routers/receipts_router.py`
- **POST /api/v1/receipts**: Create receipt
- **GET /api/v1/receipts/{id}**: Get receipt by ID
- **GET /api/v1/receipts/sale/{sale_id}**: Get receipt by sale ID
- **GET /api/v1/receipts/number/{receipt_number}**: Get by receipt number
- **GET /api/v1/receipts**: List receipts (date range filter)
- **GET /api/v1/receipts/{id}/pdf**: Download PDF
- **POST /api/v1/receipts/{id}/email**: Send via email (Celery task)

**Security**: All endpoints require SALES_ROLES (super_admin, admin, manager, cashier, salesperson)

### 7. Configuration
**Updated**: `backend/app/api/main.py`
- Registered receipts_router

### 8. Testing
**File**: `backend/tests/unit/domain/test_receipt.py`
- 16 unit tests covering:
  - Line item creation and validation
  - Payments with card details
  - Totals calculation
  - Receipt creation (thermal, A4)
  - Customer information
  - Total quantity calculation
  - Primary payment method selection
  - Validation errors (no items, no payments, invalid format)

## API Usage Examples

### Create Receipt
```bash
POST /api/v1/receipts
{
  "sale_id": "01SALE123",
  "receipt_number": "RCP-2025-001",
  "store_name": "Best Retail Store",
  "store_address": "123 Main Street\nAnytown, ST 12345",
  "store_phone": "(555) 123-4567",
  "store_tax_id": "12-3456789",
  "cashier_name": "Jane Doe",
  "customer_name": "John Smith",
  "customer_email": "john@example.com",
  "line_items": [
    {
      "product_name": "Wireless Mouse",
      "sku": "MOUSE-001",
      "quantity": 2,
      "unit_price": {"amount": 29.99, "currency": "USD"},
      "line_total": {"amount": 59.98, "currency": "USD"},
      "discount_amount": {"amount": 0, "currency": "USD"}
    }
  ],
  "payments": [
    {
      "payment_method": "card",
      "amount": {"amount": 64.78, "currency": "USD"},
      "reference_number": "TXN-ABC123",
      "card_last_four": "4242"
    }
  ],
  "totals": {
    "subtotal": {"amount": 59.98, "currency": "USD"},
    "tax_amount": {"amount": 4.80, "currency": "USD"},
    "discount_amount": {"amount": 0, "currency": "USD"},
    "total": {"amount": 64.78, "currency": "USD"},
    "amount_paid": {"amount": 64.78, "currency": "USD"},
    "change_given": {"amount": 0, "currency": "USD"}
  },
  "sale_date": "2025-12-06T10:30:00Z",
  "tax_rate": 8.0,
  "format_type": "thermal",
  "footer_message": "Thank you for shopping with us!"
}
```

### Download PDF
```bash
GET /api/v1/receipts/{receipt_id}/pdf
# Returns: application/pdf
# Content-Disposition: attachment; filename=receipt_RCP-2025-001.pdf
```

### Email Receipt
```bash
POST /api/v1/receipts/{receipt_id}/email
# Response:
{
  "message": "Receipt email queued for delivery",
  "task_id": "abc123-def456",
  "email": "john@example.com"
}
```

### Get Receipt by Sale ID
```bash
GET /api/v1/receipts/sale/01SALE123
```

### List Receipts
```bash
GET /api/v1/receipts?start_date=2025-12-01T00:00:00Z&end_date=2025-12-31T23:59:59Z&limit=50
```

## Database Schema

```sql
CREATE TABLE receipts (
    id VARCHAR(26) PRIMARY KEY,
    sale_id VARCHAR(26) NOT NULL UNIQUE,
    receipt_number VARCHAR(50) NOT NULL UNIQUE,
    store_name VARCHAR(200) NOT NULL,
    store_address TEXT NOT NULL,
    store_phone VARCHAR(20) NOT NULL,
    store_tax_id VARCHAR(50),
    cashier_name VARCHAR(200) NOT NULL,
    customer_name VARCHAR(200),
    customer_email VARCHAR(255),
    line_items JSON NOT NULL,
    payments JSON NOT NULL,
    totals JSON NOT NULL,
    sale_date TIMESTAMP WITH TIME ZONE NOT NULL,
    tax_rate NUMERIC(10, 4) NOT NULL,
    notes TEXT,
    footer_message VARCHAR(500),
    format_type VARCHAR(20) NOT NULL DEFAULT 'thermal',
    locale VARCHAR(10) NOT NULL DEFAULT 'en_US',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX ix_receipts_sale_id ON receipts(sale_id);
CREATE UNIQUE INDEX ix_receipts_receipt_number ON receipts(receipt_number);
CREATE INDEX ix_receipts_sale_date ON receipts(sale_date);
```

## Integration Points

### With Sales Domain
- Receipt created automatically after sale completion
- Sale ID links receipt to transaction
- Receipt contains complete sale details

### With Email System
- Celery task for async email delivery
- PDF attachment generation
- SMTP configuration in settings
- Retry on failure

### With Reporting
- Receipt history for audit trails
- Date range queries for reports
- Sales reconciliation

### Future: Print Integration
- Direct thermal printer output
- Print server integration
- Network printer support

## Technical Decisions

### JSON Storage for Complex Objects
- Line items, payments, totals stored as JSON
- Flexibility for future schema changes
- Avoids complex relational mappings
- Easy serialization/deserialization

### Two Format Types
- **Thermal (80mm)**: POS terminal receipts, compact
- **A4**: Professional receipts, email-friendly
- Format chosen at creation time

### PDF Generation with ReportLab
- Industry-standard library
- Full control over layout
- Supports both formats
- Returns bytes for easy storage/transmission

### Async Email Delivery
- Celery task prevents blocking API
- Retry logic for reliability
- Task ID returned for status tracking
- Email queued even if SMTP fails initially

## Dependencies
- **reportlab (^4.4.5)**: PDF generation
- **celery**: Async task execution
- **redis**: Celery broker
- **email**: MIME message construction

## Next Steps (Phase 12.4)

### Split Payment Functionality
1. Modify Sale entity for multiple payments
2. Create sale_payments junction table
3. Validate total payments equal sale total
4. Update sales API for payment array
5. Track payment method distribution

## Files Created/Modified
**Created (12 files)**:
- `backend/app/domain/receipts/entities.py`
- `backend/app/domain/receipts/__init__.py`
- `backend/app/application/receipts/ports.py`
- `backend/app/application/receipts/use_cases.py`
- `backend/app/application/receipts/__init__.py`
- `backend/app/infrastructure/services/receipt_pdf_generator.py`
- `backend/app/infrastructure/db/models/receipt_model.py`
- `backend/app/infrastructure/db/repositories/receipt_repository.py`
- `backend/alembic/versions/e8d28c25aa2b_create_receipts_table.py`
- `backend/app/api/schemas/receipt.py`
- `backend/app/api/routers/receipts_router.py`
- `backend/tests/unit/domain/test_receipt.py`
- `docs/phase12-3-complete.md` (this file)

**Modified (2 files)**:
- `backend/app/api/main.py` - Registered receipts_router
- `backend/app/infrastructure/tasks/email_tasks.py` - Added send_receipt_email task

## Compliance with Playbook
✅ **Domain-Driven**: Receipt aggregate with value objects  
✅ **Ports & Adapters**: IReceiptRepository abstraction  
✅ **Repository Pattern**: SQLAlchemy implementation  
✅ **ULID Identifiers**: Receipt IDs use `generate_ulid()`  
✅ **Money Value Object**: All amounts use `Money(Decimal, str)`  
✅ **Async/Await**: All repository methods async  
✅ **Error Handling**: NotFoundError for missing receipts  
✅ **Dependency Injection**: FastAPI Depends() for repositories  
✅ **Celery Integration**: Async email task with retry logic  

## Status
✅ **Phase 12.3 Complete** - Receipt generation system with PDF output (thermal/A4), email delivery, and receipt history.

---

**Phase Progress**: 12.3 of 12.7 (43% of Phase 12)  
**Overall Progress**: 12 of 23 phases (52%)
