
# Copilot instructions (Retail POS)

## Big picture
- This repo is a multi-app Python workspace:
	- `backend/`: FastAPI + SQLAlchemy async + Alembic + Celery/Redis.
	- `modern_client/`: Flet desktop POS client (currently mostly mocked).
	- `super_admin_client/`: SuperAdmin portal (Python client scaffold).

## Backend architecture (Clean Architecture)
- Keep business rules in `backend/app/domain/` (no FastAPI/SQLAlchemy imports).
- Put orchestration in `backend/app/application/` (use cases + ports). Prefer raising domain errors from `app.domain.common.errors`.
- Keep HTTP concerns in `backend/app/api/` (routers/schemas/dependencies/middleware). Routers should instantiate repos + use-cases and map domain → schema (see `backend/app/api/routers/products_router.py`).
- Implement ports in `backend/app/infrastructure/` (DB repos, tasks, websocket, external services).

## Multi-tenancy & data isolation
- Tenant is extracted from JWT by `TenantContextMiddleware` in `backend/app/core/tenant.py` (contextvars).
- Repositories must filter by tenant_id when available (see `get_current_tenant_id()` usage in `backend/app/infrastructure/db/repositories/inventory_repository.py` and helpers in `backend/app/infrastructure/db/repositories/tenant_aware_base.py`).

## Concurrency & optimistic locking
- Aggregates use a `version` field; writes should require `expected_version` and update via `WHERE id=:id AND version=:expected_version` (see `SqlAlchemyProductRepository.update`).

## Real-time + background work
- WebSocket events are broadcast via Redis pub/sub (`pos:events:{tenant_id}`) using `EventDispatcher` in `backend/app/infrastructure/websocket/event_dispatcher.py`.
- Celery is configured in `backend/app/infrastructure/tasks/celery_app.py`; docker compose runs worker/beat/flower (`docker-compose.dev.yml`).

## Config, logging, and security conventions
- Settings come from `.env` / `.env.local` via `backend/app/core/settings.py`. In `staging`/`prod`, wildcards are rejected (e.g., `ALLOWED_HOSTS` cannot contain `*`).
- Logging is JSON `structlog` with automatic PII masking (see `backend/app/core/logging.py`). Don’t log raw secrets/tokens/passwords.

## Developer workflows (Windows-friendly)
- Full dev stack (Postgres + Redis + API + Celery): `./scripts/dev_env_up.ps1` (uses `docker-compose.dev.yml`). Stop: `./scripts/dev_env_down.ps1`.
- Run backend locally:
	- `cd backend; py -m poetry install`
	- `py -m poetry run uvicorn app.api.main:app --reload --port 8000`
- DB bootstrap (migrations + admin user): `./scripts/db_bootstrap.ps1`.
- Quality gate used by CI: `./scripts/check_all.ps1` (requires `DATABASE_URL`).

## Testing & tooling
- Backend tooling is strict: ruff (line length 120) + mypy strict in `backend/pyproject.toml` (tests/alembic are relaxed via overrides).
- Tests are run from `backend/` with Poetry: `poetry run pytest` (typically requires Postgres configured via `DATABASE_URL`).

