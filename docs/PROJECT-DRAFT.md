# 🏪 Retail POS System - Project Draft

**Version:** 1.0.0  
**Status:** Production Ready (MVP Complete)  
**Date:** December 13, 2025  
**Author:** Development Team

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Project Overview](#project-overview)
3. [Architecture](#architecture)
4. [Features Inventory](#features-inventory)
5. [Technology Stack](#technology-stack)
6. [API Reference](#api-reference)
7. [Database Schema](#database-schema)
8. [Deployment Guide](#deployment-guide)
9. [Testing Strategy](#testing-strategy)
10. [Known Issues & Limitations](#known-issues--limitations)
11. [Future Roadmap](#future-roadmap)

---

## Executive Summary

### Project Status: ✅ MVP COMPLETE

| Metric | Value |
|--------|-------|
| **Phases Completed** | 22 of 23 (96%) |
| **API Endpoints** | 120+ |
| **Domain Entities** | 25+ |
| **Test Coverage** | 80%+ target |
| **Lines of Code** | ~50,000+ |

### Key Achievements
- ✅ Full Point-of-Sale functionality
- ✅ Multi-tenant architecture with row-level security
- ✅ Real-time updates via WebSocket
- ✅ Async job processing (Celery + Redis)
- ✅ AI/ML features (forecasting, fraud detection, recommendations)
- ✅ Complete security & compliance stack
- ✅ CI/CD pipeline with Docker/Kubernetes support

---

## Project Overview

### What is Retail POS?

A **modern, enterprise-grade Point-of-Sale system** designed for retail businesses. Built with Clean Architecture principles, it provides:

- **Sales Processing** - Fast checkout with multiple payment methods
- **Inventory Management** - Real-time stock tracking with intelligent forecasting
- **Customer Engagement** - Loyalty programs, marketing campaigns
- **Business Intelligence** - Advanced analytics and AI-powered insights
- **Multi-Store Support** - Multi-tenant architecture for chain operations

### Target Users

| Role | Capabilities |
|------|-------------|
| **Cashier** | Process sales, handle returns, manage shift |
| **Manager** | View reports, manage promotions, approve returns |
| **Admin** | Full system access, user management, configuration |
| **Super Admin** | Multi-tenant management, system configuration |
| **Auditor** | Read-only access to all data for compliance |

---

## Architecture

### Clean Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                         API LAYER                                │
│   FastAPI Routers │ Pydantic Schemas │ Auth │ Middleware         │
├─────────────────────────────────────────────────────────────────┤
│                      APPLICATION LAYER                           │
│          Use Cases │ Ports (Interfaces) │ DTOs                   │
├─────────────────────────────────────────────────────────────────┤
│                        DOMAIN LAYER                              │
│   Entities │ Value Objects │ Domain Events │ Business Rules      │
├─────────────────────────────────────────────────────────────────┤
│                    INFRASTRUCTURE LAYER                          │
│  SQLAlchemy Repos │ Celery Tasks │ WebSocket │ External APIs     │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
backend/
├── app/
│   ├── api/                    # FastAPI routers & schemas
│   │   ├── routers/            # 20+ router modules
│   │   ├── schemas/            # Pydantic models
│   │   └── dependencies/       # DI & auth
│   ├── application/            # Use cases & ports
│   │   ├── auth/
│   │   ├── catalog/
│   │   ├── inventory/
│   │   ├── sales/
│   │   └── ...
│   ├── domain/                 # Business logic
│   │   ├── common/             # Shared (Money, ULID, errors)
│   │   ├── catalog/
│   │   ├── inventory/
│   │   └── ...
│   ├── infrastructure/         # External adapters
│   │   ├── db/                 # SQLAlchemy models & repos
│   │   ├── tasks/              # Celery tasks
│   │   ├── websocket/          # WebSocket handlers
│   │   └── ml/                 # ML models
│   ├── core/                   # Settings, logging, security
│   └── shared/                 # Utilities
├── alembic/                    # Database migrations
├── tests/                      # Test suite
└── scripts/                    # Utility scripts
```

---

## Features Inventory

### Phase 1-10: Core POS ✅

| Feature | Description | Status |
|---------|-------------|--------|
| Product Catalog | SKU-based products with categories | ✅ |
| Inventory | Movement tracking, stock levels | ✅ |
| Sales | Multi-line transactions | ✅ |
| Returns | Full/partial with approval workflow | ✅ |
| Customers | CRM with lifecycle analytics | ✅ |
| Suppliers | Vendor management | ✅ |
| Purchase Orders | PO creation and receiving | ✅ |
| Employees | HR management with salary tracking | ✅ |
| Authentication | JWT + refresh tokens | ✅ |
| RBAC | 6-role permission system | ✅ |

### Phase 11: Real-Time ✅

| Feature | Description |
|---------|-------------|
| WebSocket | Authenticated real-time connection |
| 18 Event Types | Sales, inventory, presence, system |
| Redis Pub/Sub | Scalable event distribution |
| Connection Manager | Tenant/user/role aware |

### Phase 12: Advanced POS ✅

| Feature | Description |
|---------|-------------|
| Payments | Stripe integration, cash/card/gift card |
| Promotions | Percentage, fixed, BOGO, coupons |
| Receipts | PDF generation (80mm thermal + A4) |
| Split Payments | Multiple payment methods per sale |
| Gift Cards | Full lifecycle management |
| Cash Drawer | Session management, reconciliation |
| Shift Management | Start/end with cash tracking |

### Phase 13: Inventory Intelligence ✅

| Feature | Description |
|---------|-------------|
| ABC Analysis | Categorize products by value |
| Demand Forecasting | Exponential smoothing + seasonality |
| PO Suggestions | Automated reorder recommendations |
| Vendor Scoring | Performance metrics and ranking |
| Stock Alerts | WebSocket-based low/out-of-stock |
| PO Drafts | Budget-aware auto-generation |

### Phase 14-16: Business Tools ✅

| Feature | Description |
|---------|-------------|
| Custom Reports | Builder with PDF/Excel/CSV export |
| Analytics | Sales trends, inventory turnover |
| Campaigns | Email/SMS/Push marketing |
| Loyalty | Points, tiers, rewards |
| Security | Rate limiting, PII encryption, audit |

### Phase 17-21: Infrastructure ✅

| Feature | Description |
|---------|-------------|
| Multi-Tenant | Row-level security |
| API Keys | 11 permission scopes |
| Webhooks | 24 event types with HMAC |
| Observability | Prometheus + Grafana |
| CI/CD | GitHub Actions + Kubernetes |

### Phase 23: AI/ML ✅

| Model | Purpose |
|-------|---------|
| Demand Forecasting | Prophet + XGBoost ensemble |
| Churn Prediction | XGBoost classifier with RFM |
| Fraud Detection | Isolation Forest anomaly |
| Recommendations | Association rules + collaborative |

---

## Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Core language |
| FastAPI | 0.109+ | Web framework |
| SQLAlchemy | 2.0+ | ORM (async) |
| Pydantic | 2.0+ | Validation |
| Celery | 5.3+ | Task queue |
| Redis | 7+ | Cache & pub/sub |
| PostgreSQL | 15+ | Database |
| Alembic | 1.12+ | Migrations |

### ML/AI

| Library | Purpose |
|---------|---------|
| scikit-learn | ML models |
| XGBoost | Gradient boosting |
| Prophet | Time series |
| mlxtend | Association rules |

### DevOps

| Tool | Purpose |
|------|---------|
| Docker | Containerization |
| Docker Compose | Local development |
| GitHub Actions | CI/CD |
| Kubernetes | Production deployment |
| Prometheus | Metrics |
| Grafana | Dashboards |

### Frontend

| Technology | Purpose |
|------------|---------|
| Flet | Desktop client (Python) |
| httpx | HTTP client |

---

## API Reference

### Endpoint Categories

| Category | Count | Base Path |
|----------|-------|-----------|
| Auth | 12 | `/api/v1/auth` |
| Products | 10 | `/api/v1/products` |
| Categories | 2 | `/api/v1/categories` |
| Inventory | 15 | `/api/v1/inventory` |
| Sales | 3 | `/api/v1/sales` |
| Returns | 3 | `/api/v1/returns` |
| Customers | 7 | `/api/v1/customers` |
| Suppliers | 5 | `/api/v1/suppliers` |
| Purchases | 4 | `/api/v1/purchases` |
| Employees | 7 | `/api/v1/employees` |
| Payments | 5 | `/api/v1/payments` |
| Promotions | 8 | `/api/v1/promotions` |
| Receipts | 7 | `/api/v1/receipts` |
| Gift Cards | 5 | `/api/v1/gift-cards` |
| Reports | 10 | `/api/v1/reports` |
| Analytics | 7 | `/api/v1/analytics` |
| Monitoring | 9 | `/api/v1/monitoring` |
| ML | 8 | `/api/v1/ml` |
| WebSocket | 3 | `/api/v1/ws` |

### Authentication

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

### Rate Limiting

- Default: 100 requests/minute per user
- Burst: 20 requests/second
- API Keys: Configurable per key

---

## Database Schema

### Core Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| users | User accounts | id, email, role, tenant_id |
| products | Product catalog | id, sku, name, price |
| categories | Product categories | id, name, parent_id |
| inventory_movements | Stock changes | id, product_id, quantity, type |
| sales | Transactions | id, customer_id, total, status |
| sale_items | Line items | id, sale_id, product_id, quantity |
| customers | Customer data | id, email, loyalty_tier |
| suppliers | Vendor info | id, name, email |
| purchase_orders | PO records | id, supplier_id, status |

### Multi-Tenant

All business tables include:
- `tenant_id` - Foreign key to tenants table
- Repository layer automatically filters by tenant

---

## Deployment Guide

### Prerequisites

- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+

### Quick Start

```bash
# Clone repository
git clone https://github.com/Arslan1Ali/Point-OF-Sale.git
cd Point-OF-Sale

# Start infrastructure
./scripts/dev_env_up.ps1  # Windows
./scripts/dev_env_up.sh   # Linux/Mac

# Run migrations
cd backend
alembic upgrade head

# Create admin user
python scripts/create_admin_user.py

# Start server
uvicorn app.api.main:app --reload
```

### Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/retail_pos

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Stripe (optional)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### Docker Compose

```yaml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: retail_pos
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: 1234
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    command: uvicorn app.api.main:app --host 0.0.0.0
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
```

---

## Testing Strategy

### Test Categories

| Type | Location | Coverage |
|------|----------|----------|
| Unit | `tests/unit/` | Domain entities, use cases |
| Integration | `tests/integration/` | API endpoints, database |
| E2E | `tests/integration/api/test_phase12_e2e.py` | Full workflows |

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific category
pytest tests/unit/
pytest tests/integration/
```

### Test Configuration

Tests require PostgreSQL (SQLite has migration compatibility issues):

```bash
export DATABASE_URL="postgresql+asyncpg://postgres:1234@localhost:5432/test_db"
pytest
```

---

## Known Issues & Limitations

### Database Compatibility

| Issue | Impact | Workaround |
|-------|--------|------------|
| Migrations use PostgreSQL-specific features | SQLite not supported | Use PostgreSQL |
| JSONB columns | SQLite fails | PostgreSQL required |
| ENUM types | SQLite fails | PostgreSQL required |

### Current Limitations

1. **Mobile App** - Phase 22 not started (React Native planned)
2. **Offline Mode** - Requires mobile app for offline POS
3. **Multi-Currency** - Single currency per tenant

---

## Future Roadmap

### Phase 22: Mobile Apps (Planned)

- [ ] React Native app (iOS/Android)
- [ ] Barcode scanner integration
- [ ] Offline mode with sync
- [ ] Mobile receipt printing
- [ ] Push notifications

### Potential Enhancements

- [ ] Multi-currency support
- [ ] Advanced inventory (batch tracking, expiry)
- [ ] Kitchen display system (restaurant POS)
- [ ] Table management (hospitality)
- [ ] Appointment scheduling (service businesses)

---

## Appendix

### API Endpoint Quick Reference

```
# Health
GET  /health
GET  /metrics

# Auth
POST /api/v1/auth/login
POST /api/v1/auth/register
GET  /api/v1/auth/me

# Products
GET  /api/v1/products
POST /api/v1/products
GET  /api/v1/products/{id}

# Sales
POST /api/v1/sales
GET  /api/v1/sales
GET  /api/v1/sales/{id}

# Intelligence
GET  /api/v1/inventory/intelligence
GET  /api/v1/inventory/intelligence/abc
GET  /api/v1/inventory/intelligence/forecast
GET  /api/v1/inventory/intelligence/vendors
GET  /api/v1/inventory/intelligence/po-drafts

# ML
POST /api/v1/ml/train/demand-forecast
POST /api/v1/ml/predict/demand
POST /api/v1/ml/score/fraud
GET  /api/v1/ml/recommendations/{customer_id}
```

### Default Credentials

```
Email: admin@retailpos.com
Password: AdminPass123!
Role: ADMIN
```

---

**Document Version:** 1.0.0  
**Last Updated:** December 13, 2025  
**Status:** ✅ Production Ready
