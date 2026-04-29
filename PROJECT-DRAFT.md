# Retail POS System

A modern, cloud-ready Point of Sale system built with Python, FastAPI, and Clean Architecture principles.

---

## 🎯 Project Overview

**Retail POS** is a comprehensive multi-tenant point-of-sale solution designed for retail businesses. It provides complete sales management, inventory tracking, employee management, customer engagement, and real-time analytics.

### Key Highlights

| Feature | Description |
|---------|-------------|
| **Architecture** | Clean Architecture with Domain-Driven Design |
| **Backend** | FastAPI + SQLAlchemy 2.0 (async) |
| **Database** | PostgreSQL (prod) / SQLite (dev) |
| **Real-Time** | WebSocket with Redis pub/sub |
| **Background Jobs** | Celery with Redis broker |
| **Authentication** | JWT with RBAC (6 roles) |
| **Multi-Tenant** | Row-level security isolation |
| **Observability** | Prometheus + Grafana + Sentry |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                  │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Desktop POS    │  Admin Portal   │   Mobile App (Future)       │
│  (Flet Client)  │  (Super Admin)  │   (React Native)            │
└────────┬────────┴────────┬────────┴─────────────────────────────┘
         │                 │
         ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │   FastAPI   │  │  WebSocket   │  │  Prometheus Metrics    │  │
│  │   REST API  │  │  Real-Time   │  │  /metrics endpoint     │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
└────────┬────────────────┬───────────────────────────────────────┘
         │                │
         ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     USE CASES                             │   │
│  │  Sales │ Inventory │ Customers │ Payments │ Reports      │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DOMAIN LAYER                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    ENTITIES                               │   │
│  │  Product │ Sale │ Customer │ Payment │ Inventory │ User  │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  INFRASTRUCTURE LAYER                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐  │
│  │ PostgreSQL │  │   Redis    │  │   Celery   │  │  Sentry   │  │
│  │ (Database) │  │  (Cache)   │  │  (Tasks)   │  │ (Errors)  │  │
│  └────────────┘  └────────────┘  └────────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Core Modules

### 1. Sales & POS
- Multi-line sales with discounts
- Split payments (cash, card, gift card)
- Returns and refunds
- Receipt generation (PDF, thermal)
- Hold/recall transactions

### 2. Inventory Management
- Real-time stock tracking
- Low stock alerts (WebSocket)
- ABC classification
- Demand forecasting
- Supplier link management

### 3. Product Catalog
- Categories & subcategories
- Barcode/SKU management
- Bulk CSV import
- Price management
- Product images

### 4. Customer Management
- Customer profiles
- Purchase history
- Loyalty points
- Customer analytics
- GDPR-compliant data handling

### 5. Payment Processing
- Cash payments
- Card integration (Stripe)
- Gift cards (full lifecycle)
- Split payments
- Refund management

### 6. Employee Management
- Role-based access (6 roles)
- Shift management
- Performance tracking
- Salary & bonus management

### 7. Reporting & Analytics
- Sales dashboards
- Inventory reports
- Customer analytics
- Scheduled reports (PDF/Excel/CSV)
- Real-time metrics

### 8. Customer Engagement
- Marketing campaigns
- Email/SMS notifications
- Customer feedback
- Loyalty programs

---

## 🔐 Security Features

| Feature | Implementation |
|---------|----------------|
| **Authentication** | JWT with refresh tokens |
| **Password Security** | Argon2 hashing |
| **Authorization** | RBAC with 6 roles |
| **Data Encryption** | Fernet for PII |
| **Rate Limiting** | Redis-backed |
| **Audit Logging** | Full audit trail |
| **Multi-Tenant** | Row-level security |

### User Roles

| Role | Permissions |
|------|-------------|
| `super_admin` | Full system access, tenant management |
| `admin` | Store management, all operations |
| `manager` | Reports, inventory, employee oversight |
| `cashier` | Sales, returns, basic operations |
| `inventory_clerk` | Stock management only |
| `viewer` | Read-only access |

---

## 🚀 Technology Stack

### Backend
| Technology | Purpose |
|------------|---------|
| Python 3.11+ | Core language |
| FastAPI | REST API framework |
| SQLAlchemy 2.0 | Async ORM |
| Pydantic v2 | Data validation |
| Alembic | Database migrations |
| Celery | Background tasks |
| Redis | Cache, pub/sub, rate limiting |

### Database
| Environment | Database |
|-------------|----------|
| Development | SQLite (aiosqlite) |
| Production | PostgreSQL (asyncpg) |

### Observability
| Tool | Purpose |
|------|---------|
| Prometheus | Metrics collection |
| Grafana | Dashboards |
| Sentry | Error tracking |
| Structlog | JSON logging |

### DevOps
| Tool | Purpose |
|------|---------|
| Docker | Containerization |
| GitHub Actions | CI/CD pipeline |
| Kubernetes | Orchestration |

---

## 📁 Project Structure

```
retail-pos/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers & schemas
│   │   │   ├── routers/      # 28 API routers
│   │   │   ├── schemas/      # Pydantic request/response
│   │   │   └── dependencies/ # Auth, pagination
│   │   ├── application/      # Use cases (business logic)
│   │   │   ├── catalog/      # Product operations
│   │   │   ├── sales/        # Sale transactions
│   │   │   ├── inventory/    # Stock management
│   │   │   └── ...
│   │   ├── domain/           # Pure business entities
│   │   │   ├── common/       # Value objects (Money, ULID)
│   │   │   ├── catalog/      # Product, Category
│   │   │   ├── sales/        # Sale, SaleItem
│   │   │   └── ...
│   │   ├── infrastructure/   # External adapters
│   │   │   ├── db/           # SQLAlchemy models & repos
│   │   │   ├── celery/       # Background tasks
│   │   │   ├── websocket/    # Real-time events
│   │   │   └── observability/# Metrics, tracing
│   │   ├── core/             # Settings, logging
│   │   └── shared/           # Utilities
│   ├── alembic/              # Database migrations (36+)
│   ├── tests/                # Unit & integration tests
│   └── docker/               # Dockerfile, Grafana
├── modern_client/            # Flet desktop POS client
├── super_admin_client/       # Admin portal
├── scripts/                  # Dev & deploy scripts
│   ├── deploy/               # K8s manifests
│   ├── check_all.ps1         # Quality checks
│   └── dev_env_up.ps1        # Start dev stack
├── docs/                     # Documentation
└── .github/
    └── workflows/            # CI/CD pipelines
```

---

## 🛠️ Development Setup

### Prerequisites
- Python 3.11+
- Poetry (package manager)
- Docker & Docker Compose
- PostgreSQL 15+ (optional, SQLite for dev)
- Redis 7+ (optional for dev)

### Quick Start

```powershell
# 1. Clone the repository
git clone https://github.com/your-org/retail-pos.git
cd retail-pos

# 2. Start development services (Postgres + Redis)
./scripts/dev_env_up.ps1

# 3. Install backend dependencies
cd backend
poetry install

# 4. Run database migrations
poetry run alembic upgrade head

# 5. Create admin user
poetry run python scripts/create_admin_user.py

# 6. Start the API server
poetry run uvicorn app.api.main:app --reload --port 8000

# 7. Access the API docs
# http://localhost:8000/docs
```

### Environment Variables

Create `backend/.env`:

```env
ENV=dev
DEBUG=true
DATABASE_URL=postgresql+asyncpg://postgres:1234@localhost:5432/retail_pos_db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-secret-key
JWT_ISSUER=retail-pos
```

---

## 🧪 Testing

```powershell
# Run all quality checks (lint, type check, security, tests)
./scripts/check_all.ps1

# Run unit tests only
cd backend
poetry run pytest tests/unit -v

# Run integration tests (requires database)
poetry run pytest tests/integration -v

# Run with coverage
poetry run pytest --cov=app --cov-report=html
```

### Test Coverage
- **Unit Tests:** 236+ tests
- **Integration Tests:** 33+ test files
- **Coverage Target:** 80%

---

## 🚢 Deployment

### Docker

```bash
# Build the image
docker build -t retail-pos:latest -f backend/docker/Dockerfile backend/

# Run with Docker Compose
docker-compose -f docker-compose.dev.yml up
```

### Kubernetes

```bash
# Deploy to staging
./scripts/deploy/deploy-staging.sh develop-abc123

# Deploy to production
./scripts/deploy/deploy-production.sh main-abc123
```

### CI/CD Pipeline

GitHub Actions workflows:
- **Quality:** Ruff, MyPy, Bandit, pip-audit
- **Tests:** Unit + Integration with coverage
- **Build:** Docker image to GHCR
- **Deploy:** Auto-deploy to staging/production

---

## 📊 API Endpoints

### Core Endpoints

| Category | Endpoints | Description |
|----------|-----------|-------------|
| Auth | `/api/v1/auth/*` | Login, refresh, logout |
| Products | `/api/v1/products/*` | CRUD, search, import |
| Categories | `/api/v1/categories/*` | Category management |
| Sales | `/api/v1/sales/*` | Create, void, returns |
| Customers | `/api/v1/customers/*` | Customer management |
| Inventory | `/api/v1/inventory/*` | Stock, movements |
| Payments | `/api/v1/payments/*` | Process payments |
| Reports | `/api/v1/analytics/*` | Dashboards, exports |

### WebSocket

```
ws://localhost:8000/api/v1/ws?token=<jwt>
```

Events: `sale.created`, `inventory.low_stock`, `payment.completed`, etc.

---

## 📈 Observability

### Metrics Endpoint
```
GET /metrics
```

### Grafana Dashboard
Import from: `backend/docker/grafana/retail-pos-dashboard.json`

### Health Check
```
GET /health
```

---

## 📋 Project Status

| Phase | Completion |
|-------|------------|
| Core POS (Phases 1-10) | ✅ 100% |
| Real-Time (Phase 11) | ✅ 100% |
| Advanced POS (Phase 12) | ✅ 100% |
| Inventory Intelligence (Phase 13) | ✅ 100% |
| Reporting (Phase 14) | ✅ 100% |
| Customer Engagement (Phase 15) | ✅ 100% |
| Security (Phase 16) | ✅ 100% |
| Multi-Tenant (Phase 17) | ✅ 100% |
| Async Jobs (Phase 18) | ✅ 100% |
| API Layer (Phase 19) | ✅ 100% |
| Observability (Phase 20) | ✅ 100% |
| DevOps (Phase 21) | ✅ 100% |
| Mobile (Phase 22) | ❌ 0% |
| AI Features (Phase 23) | ✅ 100% |

**Overall: 96% Complete (22 of 23 Phases) - MVP READY**

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run quality checks (`./scripts/check_all.ps1`)
4. Commit your changes
5. Push and open a Pull Request

---

## 📄 License

This project is proprietary software. All rights reserved.

---

## 📞 Support

- **Documentation:** `docs/` directory
- **Issues:** GitHub Issues
- **Email:** support@retailpos.example.com
