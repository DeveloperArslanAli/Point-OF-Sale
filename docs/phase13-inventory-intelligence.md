# Phase 13 – Inventory Intelligence (Plan + Gaps)

## Scope & Current Status
- Live now: inventory insights (/inventory/intelligence), ABC classification, demand/stockout forecast, vendor performance, PO suggestions.
- Not yet covered: supplier-aware auto-PO drafting, real-time low-stock/stockout alerts, receiving exceptions (partial/returns), smarter forecasting models, desktop wiring.

## Functional Backlog (FR)
- Auto-PO drafts: generate purchase orders per preferred supplier with lead-time and unit-cost selection; emit draft for review/submit.
- Supplier selection: rank suppliers by SLA (avg lead time, on-time %, open orders), currency, and unit cost when generating POs.
- Alerting: push low-stock/stockout events via WebSocket + optional email/SMS hooks; throttle to avoid spam.
- Receiving exceptions: support partial receipts, damaged/returned quantities, and auto-adjust movements.
- Replenishment calendar: allow day-of-week blackout and safety-stock multipliers by ABC class/seasonality.
- Forecasting upgrade: add exponential smoothing/seasonality + model freshness guardrails; async recompute via Celery.
- Budget & currency: show estimated spend (per currency) alongside PO suggestions and enforce configurable spend caps.
- Desktop parity: surface insights/PO suggestions in desktop client with role-aware views.

## Non-Functional Backlog (NFR)
- Performance: p95 < 200ms for intelligence endpoints on Postgres; cache hot paths; paginate heavy responses.
- Reliability: idempotent tasks and retries for async forecasts; guardrails on stale data (timestamp + TTL in responses).
- Observability: metrics for forecast/PO suggestion latency, cache hit rate, and alert volume; trace attributes for product_id/supplier_id.
- Security: enforce INVENTORY/PURCHASING roles on new endpoints; audit log PO draft creation/submit; validate tenant boundaries when multi-tenant lands.
- Data quality: unit/integration coverage for calculations; schema validation for supplier mappings; backfill scripts for lead-time history.

## Phase Slices
- 13.1 Foundations (done): insights, ABC, forecast, vendor performance, PO suggestions.
- 13.2 Procurement automation: PO drafts with supplier ranking + spend estimate in responses.
- 13.3 Alerting: low-stock/stockout WebSocket events + throttling.
- 13.4 Forecasting v2: smoothing/seasonality via Celery jobs; freshness headers.
- 13.5 Client parity: desktop UI for insights, vendor scorecard, and PO workflow.

## Acceptance Reminders
- Tests: integration API coverage for each slice; calculation unit tests with deterministic fixtures.
- Outputs include `generated_at`, parameters echoed, currency-aware totals, and data freshness metadata where applicable.
- Roles: MANAGER/INVENTORY/PURCHASING only; audit events for PO lifecycle.
