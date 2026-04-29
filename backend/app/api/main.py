from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
import structlog

from app.api.middleware.error_handler import DomainErrorMiddleware
from app.api.middleware.rate_limiter import RateLimitMiddleware, create_rate_limiter_with_redis
from app.api.middleware.security_headers import SecurityHeadersMiddleware
from app.api.middleware.ip_allowlist import create_ip_allowlist_middleware
from app.core.login_lockout import create_login_lockout_service
from app.infrastructure.observability.tracing import (
    setup_tracing,
    instrument_fastapi,
    instrument_redis,
)
from app.infrastructure.observability.sentry import setup_sentry
from app.api.routers import (
    analytics_router,
    api_keys_router,
    auth_router,
    billing_router,
    cash_drawer_router,
    categories_router,
    customers_router,
    employees_router,
    engagement_router,
    gdpr_router,
    gift_cards_router,
    inventory_intelligence_router,
    inventory_router,
    loyalty_router,
    ml_router,
    monitoring_router,
    payments_router,
    product_supplier_links_router,
    products_router,
    promotions_router,
    purchases_router,
    receipts_router,
    registration_router,
    reports_router,
    returns_router,
    sales_router,
    settings_router,
    shift_router,
    super_admin_router,
    super_admin_v2_router,
    supplier_ranking_weights_router,
    suppliers_router,
    sync_router,
    tenants_router,
    webhooks_router,
    websocket_router,
)
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.core.tenant import TenantContextMiddleware
from app.infrastructure.observability.metrics import setup_metrics
from app.infrastructure.websocket.connection_manager import connection_manager
from app.infrastructure.websocket.event_dispatcher import EventDispatcher, set_event_dispatcher

configure_logging()
settings = get_settings()
logger = structlog.get_logger(__name__)

# Setup OpenTelemetry tracing if enabled
if settings.OTEL_ENABLED:
    tracing_enabled = setup_tracing(
        service_name=settings.OTEL_SERVICE_NAME,
        otlp_endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
    )
    if tracing_enabled:
        instrument_redis()
        logger.info("opentelemetry_tracing_configured")

# Setup Sentry error tracking if DSN is configured
if settings.SENTRY_DSN:
    sentry_enabled = setup_sentry(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
    )
    if sentry_enabled:
        logger.info("sentry_error_tracking_configured")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # pragma: no cover - minimal hook
    # Startup: Initialize event dispatcher
    event_dispatcher = EventDispatcher(
        connection_manager=connection_manager,
        redis_url=settings.CELERY_BROKER_URL,
    )
    set_event_dispatcher(event_dispatcher)
    started = await event_dispatcher.start()
    if not started:
        logger.warning(
            "event_dispatcher_disabled",
            reason="redis_unavailable",
            redis_url=settings.CELERY_BROKER_URL,
        )
    else:
        logger.info(
            "event_dispatcher_enabled",
            redis_url=settings.CELERY_BROKER_URL,
        )
    
    # Initialize rate limiter with Redis
    rate_limiter = await create_rate_limiter_with_redis(settings.REDIS_URL)
    app.state.rate_limiter = rate_limiter
    
    # Initialize login lockout service with Redis
    lockout_service = await create_login_lockout_service(settings.REDIS_URL)
    app.state.lockout_service = lockout_service
    
    yield
    
    # Shutdown: Stop event dispatcher
    await event_dispatcher.stop()

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Instrument FastAPI with OpenTelemetry if enabled
if settings.OTEL_ENABLED:
    instrument_fastapi(app)

# Middleware stack (order matters - first added = last executed)
app.add_middleware(DomainErrorMiddleware)
app.add_middleware(RateLimitMiddleware)  # Uses app.state.rate_limiter from lifespan
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TenantContextMiddleware)  # Extract tenant from JWT

# IP Allowlist for admin endpoints (enabled in staging/prod)
if settings.ENV in ("staging", "prod"):
    ip_allowlist = create_ip_allowlist_middleware(app)
    # Note: IP allowlist is applied via its own check, not as middleware
    # It's integrated into the middleware stack above

# Setup Prometheus metrics (adds middleware and /metrics endpoint)
setup_metrics(app)

if settings.ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )


@app.get("/health")
async def health() -> dict[str, str]:  # pragma: no cover - trivial
    return {"status": "ok"}


# Backward/forward compatibility for Postman tests expecting /api/v1/health
@app.get(f"{settings.API_V1_PREFIX}/health")
async def health_v1() -> dict[str, str]:  # pragma: no cover - trivial
    return {"status": "ok"}


app.include_router(products_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(inventory_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(inventory_intelligence_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(product_supplier_links_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(billing_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(categories_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(sales_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(customers_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(returns_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(suppliers_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(supplier_ranking_weights_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(purchases_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(employees_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(tenants_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(reports_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(monitoring_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(websocket_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(payments_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(promotions_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(receipts_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(gift_cards_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(loyalty_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(engagement_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(cash_drawer_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(shift_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(sync_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(webhooks_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(api_keys_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(registration_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(super_admin_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(super_admin_v2_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(settings_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(gdpr_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(ml_router.router, prefix=settings.API_V1_PREFIX)
