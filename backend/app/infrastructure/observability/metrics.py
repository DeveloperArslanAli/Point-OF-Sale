"""Prometheus metrics for observability.

Provides:
- HTTP request metrics (latency, count, errors)
- Business metrics (sales, inventory, users)
- System metrics (connections, queue depth)
"""

from __future__ import annotations

from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Match

# ==============================================================================
# HTTP Request Metrics
# ==============================================================================

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being processed",
    ["method", "endpoint"],
)

# ==============================================================================
# Business Metrics
# ==============================================================================

SALES_TOTAL = Counter(
    "pos_sales_total",
    "Total number of sales transactions",
    ["payment_method", "status"],
)

SALES_AMOUNT_TOTAL = Counter(
    "pos_sales_amount_total",
    "Total sales amount in cents",
    ["currency"],
)

SALES_ITEMS_TOTAL = Counter(
    "pos_sales_items_total",
    "Total number of items sold",
    ["category"],
)

INVENTORY_MOVEMENTS = Counter(
    "pos_inventory_movements_total",
    "Total inventory movements",
    ["direction", "reason"],
)

STOCK_ALERTS = Counter(
    "pos_stock_alerts_total",
    "Stock alert notifications",
    ["alert_type"],  # low_stock, out_of_stock, reorder_point
)

RETURNS_TOTAL = Counter(
    "pos_returns_total",
    "Total return transactions",
    ["reason"],
)

GIFT_CARDS_ISSUED = Counter(
    "pos_gift_cards_issued_total",
    "Total gift cards issued",
)

GIFT_CARDS_REDEEMED = Counter(
    "pos_gift_cards_redeemed_total",
    "Total gift card redemptions",
)

# ==============================================================================
# User Activity Metrics
# ==============================================================================

USER_LOGINS = Counter(
    "pos_user_logins_total",
    "Total user logins",
    ["role", "status"],  # status: success, failed
)

USER_SESSIONS_ACTIVE = Gauge(
    "pos_user_sessions_active",
    "Currently active user sessions",
)

SHIFTS_ACTIVE = Gauge(
    "pos_shifts_active",
    "Currently active cashier shifts",
)

CASH_DRAWER_OPERATIONS = Counter(
    "pos_cash_drawer_operations_total",
    "Cash drawer operations",
    ["operation_type"],  # open, close, adjustment
)

# ==============================================================================
# System Metrics
# ==============================================================================

DB_CONNECTIONS_ACTIVE = Gauge(
    "pos_db_connections_active",
    "Active database connections",
)

CELERY_TASKS_TOTAL = Counter(
    "pos_celery_tasks_total",
    "Total Celery tasks",
    ["task_name", "status"],  # status: started, success, failed
)

CELERY_QUEUE_DEPTH = Gauge(
    "pos_celery_queue_depth",
    "Celery queue depth",
    ["queue_name"],
)

WEBSOCKET_CONNECTIONS = Gauge(
    "pos_websocket_connections",
    "Active WebSocket connections",
)

# ==============================================================================
# Metric Recording Functions
# ==============================================================================


def record_sale(
    payment_method: str,
    status: str,
    amount_cents: int,
    currency: str = "USD",
    item_count: int = 1,
    category: str = "general",
) -> None:
    """Record a sale transaction in metrics.
    
    Args:
        payment_method: Payment method (cash, card, gift_card)
        status: Transaction status (completed, voided, partial)
        amount_cents: Sale amount in cents
        currency: Currency code
        item_count: Number of items in sale
        category: Product category
    """
    SALES_TOTAL.labels(payment_method=payment_method, status=status).inc()
    SALES_AMOUNT_TOTAL.labels(currency=currency).inc(amount_cents)
    SALES_ITEMS_TOTAL.labels(category=category).inc(item_count)


def record_inventory_movement(direction: str, reason: str) -> None:
    """Record an inventory movement.
    
    Args:
        direction: Movement direction (in, out)
        reason: Reason for movement (sale, return, adjustment, purchase)
    """
    INVENTORY_MOVEMENTS.labels(direction=direction, reason=reason).inc()


def record_stock_alert(alert_type: str) -> None:
    """Record a stock alert.
    
    Args:
        alert_type: Type of alert (low_stock, out_of_stock, reorder_point)
    """
    STOCK_ALERTS.labels(alert_type=alert_type).inc()


def record_return(reason: str) -> None:
    """Record a return transaction.
    
    Args:
        reason: Return reason
    """
    RETURNS_TOTAL.labels(reason=reason).inc()


def record_gift_card_issued() -> None:
    """Record a gift card issuance."""
    GIFT_CARDS_ISSUED.inc()


def record_gift_card_redeemed() -> None:
    """Record a gift card redemption."""
    GIFT_CARDS_REDEEMED.inc()


def record_login(role: str, success: bool) -> None:
    """Record a login attempt.
    
    Args:
        role: User role
        success: Whether login succeeded
    """
    status = "success" if success else "failed"
    USER_LOGINS.labels(role=role, status=status).inc()


def record_cash_drawer_operation(operation_type: str) -> None:
    """Record a cash drawer operation.
    
    Args:
        operation_type: Type of operation (open, close, adjustment)
    """
    CASH_DRAWER_OPERATIONS.labels(operation_type=operation_type).inc()


def record_celery_task(task_name: str, status: str) -> None:
    """Record a Celery task.
    
    Args:
        task_name: Name of the task
        status: Task status (started, success, failed)
    """
    CELERY_TASKS_TOTAL.labels(task_name=task_name, status=status).inc()


def set_active_sessions(count: int) -> None:
    """Set the count of active user sessions.
    
    Args:
        count: Number of active sessions
    """
    USER_SESSIONS_ACTIVE.set(count)


def set_active_shifts(count: int) -> None:
    """Set the count of active shifts.
    
    Args:
        count: Number of active shifts
    """
    SHIFTS_ACTIVE.set(count)


def set_websocket_connections(count: int) -> None:
    """Set the count of active WebSocket connections.
    
    Args:
        count: Number of connections
    """
    WEBSOCKET_CONNECTIONS.set(count)


def set_db_connections(count: int) -> None:
    """Set the count of active database connections.
    
    Args:
        count: Number of connections
    """
    DB_CONNECTIONS_ACTIVE.set(count)


def set_celery_queue_depth(queue_name: str, depth: int) -> None:
    """Set the depth of a Celery queue.
    
    Args:
        queue_name: Name of the queue
        depth: Number of tasks in queue
    """
    CELERY_QUEUE_DEPTH.labels(queue_name=queue_name).set(depth)


# ==============================================================================
# Metrics Middleware
# ==============================================================================


def _get_path_template(request: Request) -> str:
    """Get the path template for a request (with path params as placeholders).
    
    Args:
        request: FastAPI request
        
    Returns:
        Path template string
    """
    app: FastAPI = request.app
    
    for route in app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return getattr(route, "path", request.url.path)
    
    return request.url.path


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process request and record metrics."""
        method = request.method
        path = _get_path_template(request)
        
        # Skip metrics endpoint itself
        if path == "/metrics":
            return await call_next(request)
        
        # Track in-progress requests
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=path).inc()
        
        # Time the request
        import time
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            # Record duration
            duration = time.perf_counter() - start_time
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                endpoint=path,
            ).observe(duration)
            
            # Record request count
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=path,
                status_code=str(status_code),
            ).inc()
            
            # Decrement in-progress
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=path).dec()
        
        return response


# ==============================================================================
# Metrics Endpoint
# ==============================================================================


def metrics_endpoint() -> Response:
    """Generate Prometheus metrics response.
    
    Returns:
        Response with metrics in Prometheus format
    """
    metrics_output = generate_latest()
    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST,
    )


def setup_metrics(app: FastAPI) -> None:
    """Setup Prometheus metrics for a FastAPI application.
    
    Adds:
    - PrometheusMiddleware for HTTP metrics
    - /metrics endpoint
    
    Args:
        app: FastAPI application
    """
    app.add_middleware(PrometheusMiddleware)
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)
