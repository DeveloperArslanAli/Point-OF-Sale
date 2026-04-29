# 🏪 Enterprise Retail POS System

[![CI/CD](https://github.com/Arslan1Ali/Point-OF-Sale/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Arslan1Ali/Point-OF-Sale/actions/workflows/ci-cd.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, enterprise-grade **Point-of-Sale system** built with **Clean Architecture**, featuring real-time updates, multi-tenant support, async job processing, and comprehensive business intelligence.

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [API Documentation](#-api-documentation)
- [Development](#-development)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### Core POS Operations
- **Product Management** - Full catalog with categories, SKU lookup, CSV import
- **Sales Processing** - Multi-line transactions, split payments, discounts
- **Inventory Tracking** - Real-time stock levels, movement history, alerts
- **Returns & Refunds** - Full/partial returns with approval workflow
- **Customer Management** - CRM with lifecycle analytics, loyalty programs

### Enterprise Features
- **Multi-Tenant Architecture** - Isolated data per tenant with subscription plans
- **Role-Based Access Control** - 6 roles (Super Admin, Admin, Manager, Cashier, Auditor, User)
- **Real-Time Updates** - WebSocket-based live notifications (18 event types)
- **Async Job Processing** - Celery + Redis for background tasks
- **Webhook Integrations** - Event-driven integrations with HMAC signatures

### Advanced POS
- **Payment Integration** - Stripe, PayPal, Square support
- **Gift Card System** - Purchase, activate, redeem with secure codes
- **Promotion Engine** - Flexible discounts, coupons, buy-x-get-y
- **Receipt Generation** - PDF (thermal 80mm + A4), email delivery
- **Cash Drawer & Shifts** - Shift management with cash reconciliation

### Business Intelligence
- **Inventory Intelligence** - ABC analysis, demand forecasting, PO suggestions
- **Customer Engagement** - Loyalty tiers, engagement tracking, notifications
- **Reporting** - Sales analytics, inventory reports, custom report builder
- **Supplier Analytics** - Vendor performance, lead time tracking

### AI & Machine Learning
- **Demand Forecasting** - Prophet + XGBoost ensemble with trend/seasonality
- **Customer Churn Prediction** - XGBoost classifier with RFM features
- **Fraud Detection** - Isolation Forest anomaly detection + rule-based triggers
- **Product Recommendations** - Association rules + collaborative filtering

### Operations & DevOps
- **Observability** - Prometheus metrics, Grafana dashboards, structured logging
- **CI/CD Pipeline** - GitHub Actions with automated testing & deployment
- **Docker Support** - Full containerization with Docker Compose

---

## 🏗 Architecture

### Clean Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                            │
│         FastAPI Routers • Pydantic Schemas • Auth           │
├─────────────────────────────────────────────────────────────┤
│                    Application Layer                        │
│              Use Cases • Ports (Interfaces)                 │
├─────────────────────────────────────────────────────────────┤
│                      Domain Layer                           │
│      Entities • Value Objects • Domain Events • Rules       │
├─────────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                      │
│   SQLAlchemy Repos • Celery Tasks • WebSocket • External    │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Patterns

| Pattern | Implementation |
|---------|----------------|
| **Repository** | Protocol-based abstractions with SQLAlchemy adapters |
| **CQRS** | Separated read/write operations in use cases |
| **Domain Events** | EventRecorderMixin for aggregate events |
| **Value Objects** | Money, ULID identifiers, typed enums |
| **Optimistic Locking** | Version fields on all aggregates |

---

## 🛠 Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **FastAPI** | Async web framework |
| **SQLAlchemy 2.0** | Async ORM with type hints |
| **Alembic** | Database migrations |
| **Pydantic 2.0** | Data validation & serialization |
| **Celery** | Distributed task queue |
| **Redis** | Cache, pub/sub, task broker |
| **PostgreSQL** | Primary database |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| **Docker** | Containerization |
| **Prometheus** | Metrics collection |
| **Grafana** | Dashboards & visualization |
| **GitHub Actions** | CI/CD pipeline |

### Security
| Technology | Purpose |
|------------|---------|
| **JWT** | Access & refresh tokens |
| **Argon2** | Password hashing |
| **HMAC-SHA256** | Webhook signatures |
| **Bandit** | Security scanning |

### Clients
| Technology | Purpose |
|------------|---------|
| **Flet** | Desktop POS client |
| **Python** | Admin portal |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ (or SQLite for development)
- Redis 7+
- Poetry (package manager)

### 1. Clone & Setup

```powershell
# Clone repository
git clone https://github.com/Arslan1Ali/Point-OF-Sale.git
cd Point-OF-Sale

# Install backend dependencies
cd backend
poetry install
```

### 2. Environment Configuration

```powershell
# Copy environment template
cp .env.example .env

# Edit configuration
# DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/retail_pos
# REDIS_URL=redis://localhost:6379/0
# SECRET_KEY=your-secret-key-here
```

### 3. Start Development Stack

```powershell
# Start PostgreSQL + Redis
./scripts/dev_env_up.ps1

# Apply migrations
poetry run alembic upgrade head

# Start API server
poetry run uvicorn app.api.main:app --reload --port 8000
```

### 4. Access Services

| Service | URL |
|---------|-----|
| API Docs | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |
| Flower (Celery) | http://localhost:5555 |
| Grafana | http://localhost:3000 |

### Default Admin Credentials
```
Email: admin@retailpos.com
Password: AdminPass123!
```

---

## 📁 Project Structure

```
retail-pos/
├── backend/                    # FastAPI Backend
│   ├── alembic/               # Database migrations
│   │   └── versions/          # 29 migration files
│   ├── app/
│   │   ├── api/               # API Layer
│   │   │   ├── routers/       # 24 route handlers
│   │   │   ├── schemas/       # Pydantic models
│   │   │   └── dependencies/  # Auth, DB session
│   │   ├── application/       # Use Cases & Ports
│   │   │   ├── auth/
│   │   │   ├── catalog/
│   │   │   ├── customers/
│   │   │   ├── inventory/
│   │   │   ├── sales/
│   │   │   └── ...
│   │   ├── domain/            # Business Logic
│   │   │   ├── auth/
│   │   │   ├── catalog/
│   │   │   ├── customers/
│   │   │   ├── gift_cards/
│   │   │   ├── inventory/
│   │   │   ├── payments/
│   │   │   ├── promotions/
│   │   │   ├── sales/
│   │   │   ├── webhooks/
│   │   │   └── ...
│   │   ├── infrastructure/    # External Adapters
│   │   │   ├── db/
│   │   │   │   ├── models/    # SQLAlchemy models
│   │   │   │   └── repositories/
│   │   │   ├── tasks/         # Celery tasks
│   │   │   ├── websocket/     # Real-time events
│   │   │   └── services/      # Email, PDF generation
│   │   ├── core/              # Cross-cutting concerns
│   │   │   ├── settings.py
│   │   │   ├── logging.py
│   │   │   └── security.py
│   │   └── shared/            # Utilities
│   ├── docker/
│   │   ├── Dockerfile
│   │   └── grafana/           # Dashboards
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   └── pyproject.toml
│
├── modern_client/             # Flet Desktop Client
│   ├── views/                 # UI screens
│   ├── services/              # API client
│   └── components/            # Reusable widgets
│
├── super_admin_client/        # Admin Portal
│   ├── views/
│   └── services/
│
├── scripts/                   # Development scripts
│   ├── check_all.ps1         # Quality checks
│   ├── dev_env_up.ps1        # Start Docker stack
│   └── db_bootstrap.ps1      # Reset database
│
├── docs/                      # Documentation
│   ├── implementation-roadmap.md
│   ├── PROJECT-STATUS-REPORT.md
│   └── phase-*.md
│
├── .github/
│   ├── workflows/
│   │   ├── ci-cd.yml         # Full CI/CD pipeline
│   │   └── pr-check.yml      # PR quality gates
│   └── dependabot.yml
│
└── docker-compose.dev.yml     # Development stack
```

---

## 📚 API Documentation

### Authentication
```http
POST /api/v1/auth/login          # Login, get tokens
POST /api/v1/auth/refresh        # Refresh access token
POST /api/v1/auth/logout         # Revoke refresh token
```

### Products & Catalog
```http
GET    /api/v1/products          # List products (paginated)
POST   /api/v1/products          # Create product
GET    /api/v1/products/{id}     # Get product details
PUT    /api/v1/products/{id}     # Update product
DELETE /api/v1/products/{id}     # Soft delete
POST   /api/v1/products/import   # Bulk CSV import
```

### Sales & Transactions
```http
POST   /api/v1/sales             # Create sale (with split payments)
GET    /api/v1/sales             # List sales (date range filter)
GET    /api/v1/sales/{id}        # Get sale details
POST   /api/v1/returns           # Process return
```

### Inventory
```http
GET    /api/v1/inventory/stock           # Current stock levels
POST   /api/v1/inventory/movements       # Record movement
GET    /api/v1/inventory/intelligence/insights    # AI-powered insights
GET    /api/v1/inventory/intelligence/forecasts   # Demand forecasting
GET    /api/v1/inventory/intelligence/po-drafts   # Auto PO suggestions
```

### Payments & Gift Cards
```http
POST   /api/v1/payments/cash             # Process cash payment
POST   /api/v1/payments/card             # Process card payment
POST   /api/v1/gift-cards/purchase       # Purchase gift card
POST   /api/v1/gift-cards/{code}/redeem  # Redeem gift card
```

### Webhooks
```http
POST   /api/v1/webhooks                  # Create subscription
GET    /api/v1/webhooks                  # List subscriptions
POST   /api/v1/webhooks/{id}/test        # Test webhook
GET    /api/v1/webhooks/{id}/deliveries  # Delivery history
```

### Real-Time (WebSocket)
```http
WS     /api/v1/ws?token={jwt}            # WebSocket connection
GET    /api/v1/ws/stats                  # Connection statistics
```

### Full API Reference
Interactive documentation available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 💻 Development

### Code Quality

```powershell
# Run all checks (linting, types, security, tests)
./scripts/check_all.ps1

# Individual commands
poetry run ruff check .              # Linting
poetry run ruff format .             # Formatting
poetry run mypy .                    # Type checking
poetry run bandit -r app/            # Security scan
poetry run pip-audit                 # Dependency vulnerabilities
```

### Database Migrations

```powershell
# Apply all migrations
poetry run alembic upgrade head

# Create new migration
poetry run alembic revision --autogenerate -m "add_new_table"

# Rollback one migration
poetry run alembic downgrade -1

# View migration history
poetry run alembic history
```

### Background Tasks

```powershell
# Start Celery worker
poetry run celery -A app.infrastructure.tasks worker -l info -Q default,imports,reports,emails

# Start Celery beat (scheduler)
poetry run celery -A app.infrastructure.tasks beat -l info

# Monitor with Flower
poetry run celery -A app.infrastructure.tasks flower --port=5555
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `sqlite+aiosqlite:///./dev.db` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key | (required) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry | `30` |
| `CORS_ORIGINS` | Allowed origins | `["*"]` |
| `SMTP_HOST` | Email server | - |
| `STRIPE_SECRET_KEY` | Stripe API key | - |

---

## 🧪 Testing

### Run Tests

```powershell
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=app --cov-report=html

# Unit tests only
poetry run pytest tests/unit/

# Integration tests only
poetry run pytest tests/integration/

# Specific test file
poetry run pytest tests/unit/domain/test_gift_card.py -v
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── domain/              # Entity tests
│   ├── application/         # Use case tests
│   └── infrastructure/      # Repository tests (mocked)
└── integration/
    ├── api/                 # Endpoint tests
    └── websocket/           # WebSocket tests
```

### Coverage Requirements
- **Minimum**: 80% overall coverage
- **Domain layer**: 90%+ recommended
- **Use cases**: 85%+ recommended

---

## 🚢 Deployment

### Docker Deployment

```powershell
# Build image
docker build -t retail-pos:latest -f backend/docker/Dockerfile backend/

# Run with Docker Compose
docker-compose -f docker-compose.dev.yml up -d
```

### Production Checklist

- [ ] Set `DEBUG=false`
- [ ] Configure PostgreSQL (not SQLite)
- [ ] Set strong `SECRET_KEY`
- [ ] Configure Redis cluster
- [ ] Enable HTTPS/TLS
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure backup strategy
- [ ] Set up log aggregation
- [ ] Enable rate limiting
- [ ] Configure CORS properly

### CI/CD Pipeline

The GitHub Actions pipeline includes:
1. **Quality Checks** - Linting, type checking, security scans
2. **Unit Tests** - Fast feedback on domain logic
3. **Integration Tests** - Full API testing with database
4. **Migration Validation** - Ensure migrations are clean
5. **Docker Build** - Build and push to registry
6. **Deployment** - Staging → Production (manual approval)

---

## 📊 Monitoring

### Grafana Dashboards

| Dashboard | Metrics |
|-----------|---------|
| **API Metrics** | Request rates, response times, error rates |
| **Business Metrics** | Sales volume, inventory levels, promotions |
| **System Metrics** | CPU, memory, queue depths, connections |

### Health Endpoints

```http
GET /health                    # Basic health check
GET /api/v1/monitoring/health  # Detailed health (DB, Redis, Celery)
GET /api/v1/monitoring/workers # Celery worker status
GET /api/v1/monitoring/queues  # Queue depths
```

### Logging

Structured JSON logging via `structlog`:
```json
{
  "timestamp": "2025-12-12T10:30:00Z",
  "level": "info",
  "event": "sale_created",
  "sale_id": "01HWXYZ...",
  "tenant_id": "01HWABC...",
  "trace_id": "abc123..."
}
```

---

## 🗺 Roadmap

### Project Status: 96% Complete (22 of 23 Phases)

### Completed ✅
- Core POS (Sales, Inventory, Returns)
- Authentication & RBAC (6 roles)
- Real-Time WebSocket (18 event types)
- Async Job Processing (Celery + Redis)
- Payment Integration (Stripe)
- Gift Card System (full lifecycle)
- Promotion Engine (discounts, coupons, BOGO)
- Receipt Generation (PDF + email)
- Customer Loyalty & Engagement
- Webhook System (24 event types)
- Multi-Tenant Row-Level Security
- CI/CD Pipeline (GitHub Actions + Kubernetes)
- Observability (Prometheus + Grafana)
- Advanced Reporting (PDF/Excel/CSV exports)
- Security & Compliance (PII encryption, rate limiting)
- API & Integration Layer (API keys, webhooks)
- Inventory Intelligence (ABC, forecasting, PO automation)
- AI/ML Features (demand forecasting, churn, fraud, recommendations)

### Planned 📋
- Mobile Apps (React Native - Phase 22)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Commit Convention
We use [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📞 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/Arslan1Ali/Point-OF-Sale/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Arslan1Ali/Point-OF-Sale/discussions)

---

<p align="center">
  Built with ❤️ using FastAPI, SQLAlchemy, and Clean Architecture
</p>
