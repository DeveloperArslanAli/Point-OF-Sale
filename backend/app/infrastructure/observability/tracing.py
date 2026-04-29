"""OpenTelemetry distributed tracing configuration.

Provides request tracing across services with:
- Automatic span creation for HTTP requests
- Database query tracing
- Redis operation tracing
- Custom span helpers for business operations
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Callable, Iterator

import structlog

logger = structlog.get_logger(__name__)

# Check if OpenTelemetry is available
_otel_available = False
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import Status, StatusCode, Span
    _otel_available = True
except ImportError:
    trace = None
    Status = None
    StatusCode = None
    Span = None


def setup_tracing(
    service_name: str = "pos-backend",
    otlp_endpoint: str | None = None,
    enable_console: bool = False,
) -> bool:
    """
    Setup OpenTelemetry tracing.
    
    Args:
        service_name: Name of the service for trace identification
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
        enable_console: Enable console exporter for debugging
        
    Returns:
        True if tracing was enabled, False otherwise
    """
    if not _otel_available:
        logger.info("opentelemetry_not_available", reason="packages_not_installed")
        return False
    
    endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    
    if not endpoint and not enable_console:
        logger.info("opentelemetry_disabled", reason="no_endpoint_configured")
        return False
    
    try:
        # Create resource with service info
        resource = Resource.create({
            "service.name": service_name,
            "service.version": os.getenv("APP_VERSION", "1.0.0"),
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        })
        
        # Create tracer provider
        provider = TracerProvider(resource=resource)
        
        # Add OTLP exporter if endpoint provided
        if endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("otlp_exporter_configured", endpoint=endpoint)
        
        # Add console exporter for debugging
        if enable_console:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.info("console_exporter_enabled")
        
        # Set global tracer provider
        trace.set_tracer_provider(provider)
        
        logger.info(
            "opentelemetry_tracing_enabled",
            service_name=service_name,
            endpoint=endpoint,
        )
        
        return True
        
    except Exception as e:
        logger.error("opentelemetry_setup_failed", error=str(e))
        return False


def instrument_fastapi(app) -> bool:
    """
    Instrument FastAPI application for automatic tracing.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        True if instrumentation succeeded
    """
    if not _otel_available:
        return False
    
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("fastapi_instrumented")
        return True
    except Exception as e:
        logger.error("fastapi_instrumentation_failed", error=str(e))
        return False


def instrument_sqlalchemy(engine) -> bool:
    """
    Instrument SQLAlchemy engine for query tracing.
    
    Args:
        engine: SQLAlchemy engine instance
        
    Returns:
        True if instrumentation succeeded
    """
    if not _otel_available:
        return False
    
    try:
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("sqlalchemy_instrumented")
        return True
    except Exception as e:
        logger.error("sqlalchemy_instrumentation_failed", error=str(e))
        return False


def instrument_redis() -> bool:
    """
    Instrument Redis for operation tracing.
    
    Returns:
        True if instrumentation succeeded
    """
    if not _otel_available:
        return False
    
    try:
        RedisInstrumentor().instrument()
        logger.info("redis_instrumented")
        return True
    except Exception as e:
        logger.error("redis_instrumentation_failed", error=str(e))
        return False


# =============================================================================
# Span Helpers
# =============================================================================


def get_tracer(name: str = "pos-backend"):
    """Get a tracer instance for creating spans."""
    if not _otel_available or trace is None:
        return _NoOpTracer()
    return trace.get_tracer(name)


class _NoOpTracer:
    """No-op tracer when OpenTelemetry is not available."""
    
    @contextmanager
    def start_as_current_span(self, name: str, **kwargs) -> Iterator[Any]:
        yield _NoOpSpan()


class _NoOpSpan:
    """No-op span for when tracing is disabled."""
    
    def set_attribute(self, key: str, value: Any) -> None:
        pass
    
    def set_status(self, status: Any) -> None:
        pass
    
    def record_exception(self, exception: Exception) -> None:
        pass
    
    def add_event(self, name: str, attributes: dict | None = None) -> None:
        pass


@contextmanager
def create_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    tracer_name: str = "pos-backend",
) -> Iterator[Any]:
    """
    Create a traced span for a business operation.
    
    Usage:
        with create_span("process_sale", {"sale_id": sale.id}) as span:
            # Business logic here
            span.set_attribute("items_count", len(items))
    
    Args:
        name: Span name
        attributes: Initial span attributes
        tracer_name: Name of the tracer
        
    Yields:
        Span object (or NoOpSpan if tracing disabled)
    """
    tracer = get_tracer(tracer_name)
    
    with tracer.start_as_current_span(name) as span:
        if attributes and hasattr(span, "set_attribute"):
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


def trace_function(name: str | None = None, attributes: dict[str, Any] | None = None):
    """
    Decorator to trace a function.
    
    Usage:
        @trace_function("process_order")
        async def process_order(order_id: str):
            ...
    
    Args:
        name: Span name (defaults to function name)
        attributes: Additional span attributes
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__
        
        if _is_async_function(func):
            async def async_wrapper(*args, **kwargs):
                with create_span(span_name, attributes) as span:
                    try:
                        result = await func(*args, **kwargs)
                        return result
                    except Exception as e:
                        if hasattr(span, "record_exception"):
                            span.record_exception(e)
                        if hasattr(span, "set_status") and StatusCode:
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                        raise
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                with create_span(span_name, attributes) as span:
                    try:
                        result = func(*args, **kwargs)
                        return result
                    except Exception as e:
                        if hasattr(span, "record_exception"):
                            span.record_exception(e)
                        if hasattr(span, "set_status") and StatusCode:
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                        raise
            return sync_wrapper
    
    return decorator


def _is_async_function(func: Callable) -> bool:
    """Check if function is async."""
    import asyncio
    return asyncio.iscoroutinefunction(func)


# =============================================================================
# Span Attribute Helpers
# =============================================================================


def add_sale_attributes(span, sale_id: str, total: float, items_count: int) -> None:
    """Add sale-related attributes to a span."""
    if hasattr(span, "set_attribute"):
        span.set_attribute("sale.id", sale_id)
        span.set_attribute("sale.total", total)
        span.set_attribute("sale.items_count", items_count)


def add_inventory_attributes(span, product_id: str, quantity: int, movement_type: str) -> None:
    """Add inventory-related attributes to a span."""
    if hasattr(span, "set_attribute"):
        span.set_attribute("inventory.product_id", product_id)
        span.set_attribute("inventory.quantity", quantity)
        span.set_attribute("inventory.movement_type", movement_type)


def add_customer_attributes(span, customer_id: str, action: str) -> None:
    """Add customer-related attributes to a span."""
    if hasattr(span, "set_attribute"):
        span.set_attribute("customer.id", customer_id)
        span.set_attribute("customer.action", action)


def add_tenant_attributes(span, tenant_id: str) -> None:
    """Add tenant context to a span."""
    if hasattr(span, "set_attribute"):
        span.set_attribute("tenant.id", tenant_id)
