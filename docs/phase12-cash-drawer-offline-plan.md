# Phase 12 Cash Drawer, Shift Tracking, and Offline Plan

## Goals
- Add audited cash drawer sessions with open/close counts, cash in/out events, and over/short detection.
- Track cashier shifts (who, when, which terminal) and bind sales plus drawer events to a shift record.
- Provide an offline-first path for POS: queue sales and drawer events locally, replay safely when connectivity returns.

## Scope & Constraints
- Target FastAPI backend + desktop PySimpleGUI client; reuse existing auth/roles and structlog tracing.
- Default currency USD; multi-currency not required for drawer balances in this phase.
- SQLite (offline) ➜ Postgres (online) reconciliation must remain idempotent; avoid double posting.

## Domain Sketch
- `CashDrawerSession`: id, terminal_id, opened_by, closed_by, opening_float, closing_count, over_short, status (open/closed), opened_at/closed_at, version.
- `CashMovement`: id, drawer_session_id, type (pay_in/payout/sale_change), amount, reason, reference (sale_id or note), created_at.
- `Shift`: id, user_id, terminal_id, started_at/ended_at, status (active/closed), total_sales, cash_sales, non_cash_sales.
- Linkages: Sale references `shift_id`; drawer movements reference sale_id when generated from change due.

## API/Use Case Plan
1. **Open Drawer**: POST `/cash-drawers/open` with opening float + terminal; returns session id. Validate no active session for terminal.
2. **Close Drawer**: POST `/cash-drawers/{id}/close` with counted totals; backend computes over/short and locks session.
3. **Pay In/Out**: POST `/cash-drawers/{id}/movements` for petty cash or drops; append CashMovement and update running drawer balance.
4. **Shift Start/End**: POST `/shifts/start` and `/shifts/{id}/end`; enforce one active shift per user/terminal; roll up totals on close.
5. **Sale Binding**: RecordSaleUseCase accepts optional `shift_id`; when payment_method is `cash`, emit a CashMovement of type `sale_change` for drawer.
6. **Reporting**: GET endpoints for drawer session detail, over/short summary, and shift history; include pagination and filters by terminal/user/date.

## Persistence & Migrations
- New tables: `cash_drawer_sessions`, `cash_movements`, `shifts`.
- Indexes: session status + terminal, shift status + user, movement drawer_id + created_at.
- Foreign keys: sale_id (nullable) on cash_movements; shift_id on sales.
- Optimistic locking: version columns on sessions and shifts; reuse existing ULID ids.

## Offline Strategy
- Desktop client caches `shift_id` and `drawer_session_id` locally once opened.
- When offline: store sales + movements in a local queue with ULID ids, timestamps, and an idempotency key; mark dependencies (shift/drawer ids).
- Replay rules on reconnect:
  - Upsert shift and drawer sessions by id; if session already closed in cloud, halt replay and prompt for manual resolution.
  - Post sales first, then cash movements referencing the persisted sale ids (map via idempotency key).
  - If any replay step fails, stop and surface a reconciliation task list (failed ids + reason).
- Add a `/sync/replay` endpoint that accepts a batch and enforces idempotency via `external_id` + `source=offline` fields.

## Auditing & Observability
- Bind `trace_id` across sale ➜ cash movement ➜ drawer session logs; include terminal_id and shift_id in log context.
- Emit domain events: `DrawerOpened`, `DrawerClosed`, `CashMovementRecorded`, `ShiftStarted`, `ShiftEnded` for future streaming.
- Alerts: if over/short exceeds threshold, emit structured log + optional webhook (Phase 13 hook point).

## Sequencing
1. Migrations + models for drawer session, movement, shift.
2. Use cases and repository adapters; wire into RecordSale for cash payments.
3. API routers + Pydantic schemas; desktop client updates for open/close/shift start/end.
4. Offline queue format + replay endpoint; desktop client queue writer.
5. Integration tests: drawer lifecycle, shift lifecycle, sale + cash movement linkage, replay idempotency.

## Open Questions
- Do we need per-tender denomination counts on close (bills/coins) or only totals?
- Should pay-in/payout reasons be enumerated for BI (e.g., drop, safe, refund float)?
- What is the acceptable over/short threshold before blocking close vs. logging warning?
