# Next Steps & Roadmap Snapshot

This document complements the scaffold and highlights prioritized upcoming tasks derived from the architecture plan.

## Recently Completed
- **Phase 11 Real-Time Communication (December 2025):** WebSocket infrastructure with JWT auth, ConnectionManager (tenant/user/role aware), EventDispatcher (Redis pub/sub), 18 event types, 3 event handlers (Sales, Inventory, Presence), integrated with Sales/Inventory/Products endpoints. Live updates for sales, inventory alerts, price changes, and user presence.
- **Phase 18 Async Job Processing (December 2025):** Celery + Redis infrastructure, async product imports, report generation, email notifications, scheduled maintenance tasks (token cleanup, daily reports), Flower monitoring UI, 15 health check endpoints.
- Phase 10 Cashier Workflow: Implemented strict RBAC with separate layouts (Full Screen POS for Cashiers).
- Phase 10 Cashier Workflow: Implemented RBAC in Frontend (hiding Admin views for Cashiers).
- Phase 10 Cashier Workflow: Added "Create User Account" (with Role selection) to Employee Management for streamlined onboarding.
- Phase 9 Employee Management: Full implementation of Employee CRUD, Salary History, Bonuses, and Frontend Views.
- Phase 9 Employee Management: Fixed UI layout issues and improved input UX (Date Pickers).
- Phase 3 Enterprise Scale: Redis Caching implemented for `/products` and `/categories` list endpoints with invalidation on updates.
- Phase 2 Backend Hardening: Concurrency fixes (Optimistic Locking + DB Locking) for Sales recording to prevent overselling.
- Phase 1 Frontend Parity: Modern Client updated with Config, Error Handling, Orders View, and Customer Selection.
- Phase 8 backend finalization: Supplier summary now reports average lead time hours via repository analytics, rounding out procurement metrics and documentation.
- Phase 7 supplier insights: `/suppliers/{id}/summary` endpoint with purchase aggregation, formatted DTO, and end-to-end integration coverage including empty-history behaviour.
- Phase 6 returns enhancements: `/returns` list/detail endpoints with repository/query layer support and integration coverage for pagination and auth.
- Phase 5 customer insights: `/customers/{id}/summary` aggregates lifetime value, quantity, last purchase linkage, and gained coverage in integration tests.
- Phase 2 kickoff: Admin action log endpoint documented and desktop client now surfaces paginated audit history for admins.
- Desktop client admin tooling expanded with user management (list/filter, activate/deactivate, role change, password reset) backed by `/auth/users` API.
- Catalog browse foundation: `/categories` API now returns paginated results with search filters and metadata, plus refreshed tests.
- Phase 1 groundwork: Postgres-first migrations, CI plan + workflow, logging/trace utilities, observability guide, AI instructions update.
- Local parity scripts (`scripts/check_all.sh` / `.ps1`) aligned with pipeline.
- `.env` example added to streamline configuration for new contributors.
- Docker Compose dev stack (`docker-compose.dev.yml` + scripts) for backend + Postgres + Redis placeholder.
- Pre-commit hooks (`.pre-commit-config.yaml`) mirroring CI lint/type/unit checks.
- Security scanning (Bandit + pip-audit) wired into CI and local parity scripts.
- Admin lifecycle endpoints (activate/deactivate/role/password reset) added behind admin-only routes with optimistic locking and test coverage.

## High-Priority (Next Iterations)
1. **Phase 12 Advanced POS Features:** Payment integrations (Stripe/PayPal), split payments, gift cards, discounts, promotions engine.
2. **Phase 14 Advanced Reporting:** Custom report builder, scheduled reports (daily/weekly/monthly), export to PDF/Excel, data visualization.
3. **Phase 13 Customer Loyalty:** Points system, tier management, reward redemption, campaign engine.
4. Auth subsystem hardening:
   - Tie audit log view into future trace/observability dashboards and document operations runbooks
   - Evaluate lockout/throttling policy for repeated login failures
5. Customer insight follow-through: expose summary metrics in the desktop client and record acceptance feedback.
6. Supplier insights desktop integration: consume the new summary fields, add dashboards, and align with finance reporting needs.

## Medium-Term
- Inventory movement ledger & stock projection service.
- Sales transaction aggregate + atomic stock decrement.
- Purchasing follow-ups: receiving exceptions, partial deliveries, credit memo support.
- Reporting skeleton (async job pattern + materialization placeholder).
- Structured metrics (Prometheus exporter) & tracing (OpenTelemetry switch).

- Customer insights: multi-currency breakdowns, churn indicators, and event hooks once the foundational summary sees adoption.
- Returns follow-ups: reason codes, refund linkage, and event hooks once payment integration lands.

- CI pipeline: add Docker image build/push and smoke deploy once service hardened.
- Evaluate dependency update automation (Renovate/Dependabot) once CI gates in place.

## Desktop Client Upcoming
- Auth window & token persistence.
- Product list view with search hitting API.
- Sales window layout skeleton.
- Local SQLite cache + sync strategy doc.

## Data & Migration
- Decide final primary key strategy (ULID confirmed; ensure endian-friendly sorting if required).
- Baseline migration for core tables complete; next add purchase/return deltas once domains advance.

## Quality Targets
- Domain/application test coverage > 90%.
- p95 create product latency < 80ms (local env with SQLite not indicative; re-evaluate on Postgres).

## Risks / Watchlist
- Early decisions around promotions could leak into sales domain prematurely—keep postponed until pricing context is defined.
- Ensure eventual consistency for reporting does not pollute OLTP transactional paths.

---
Generated: Initial scaffold phase completion.
