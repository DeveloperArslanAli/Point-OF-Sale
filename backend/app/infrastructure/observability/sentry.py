"""Sentry error tracking integration.

Provides:
- Automatic exception capture
- Performance monitoring
- User context enrichment
- Custom tags and breadcrumbs
"""

from __future__ import annotations

import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Check if Sentry is available
_sentry_available = False
_sentry_sdk = None

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    _sentry_available = True
    _sentry_sdk = sentry_sdk
except ImportError:
    pass


def setup_sentry(
    dsn: str | None = None,
    environment: str = "development",
    release: str | None = None,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
    debug: bool = False,
) -> bool:
    """
    Initialize Sentry error tracking and performance monitoring.
    
    Args:
        dsn: Sentry DSN (can also be set via SENTRY_DSN env var)
        environment: Deployment environment name
        release: Release version string
        traces_sample_rate: Fraction of transactions to trace (0.0 - 1.0)
        profiles_sample_rate: Fraction of traces to profile (0.0 - 1.0)
        debug: Enable Sentry debug mode
        
    Returns:
        True if Sentry was initialized successfully
    """
    if not _sentry_available or _sentry_sdk is None:
        logger.info("sentry_not_available", reason="sdk_not_installed")
        return False
    
    sentry_dsn = dsn or os.getenv("SENTRY_DSN")
    
    if not sentry_dsn:
        logger.info("sentry_disabled", reason="no_dsn_configured")
        return False
    
    try:
        _sentry_sdk.init(
            dsn=sentry_dsn,
            environment=environment,
            release=release or os.getenv("APP_VERSION", "unknown"),
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            debug=debug,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration(),
                LoggingIntegration(
                    level=None,  # Don't capture logs as breadcrumbs
                    event_level=None,  # Don't capture logs as events
                ),
            ],
            # Filter out health check spam
            before_send=_before_send,
            before_send_transaction=_before_send_transaction,
        )
        
        logger.info(
            "sentry_initialized",
            environment=environment,
            traces_sample_rate=traces_sample_rate,
        )
        
        return True
        
    except Exception as e:
        logger.error("sentry_init_failed", error=str(e))
        return False


def _before_send(event: dict, hint: dict) -> dict | None:
    """
    Filter or modify events before sending to Sentry.
    
    Returns None to drop the event.
    """
    # Don't send expected errors
    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]
        
        # Skip validation errors (expected user input issues)
        if exc_type.__name__ in ("ValidationError", "RequestValidationError"):
            return None
        
        # Skip 404s
        if hasattr(exc_value, "status_code") and exc_value.status_code == 404:
            return None
        
        # Skip rate limit errors
        if exc_type.__name__ == "RateLimitExceeded":
            return None
    
    return event


def _before_send_transaction(event: dict, hint: dict) -> dict | None:
    """
    Filter transactions before sending to Sentry.
    
    Returns None to drop the transaction.
    """
    # Don't trace health checks or metrics endpoints
    transaction_name = event.get("transaction", "")
    
    skip_endpoints = ["/health", "/metrics", "/api/v1/ws"]
    for endpoint in skip_endpoints:
        if transaction_name.startswith(endpoint):
            return None
    
    return event


# =============================================================================
# Context Helpers
# =============================================================================


def set_user_context(user_id: str, email: str | None = None, role: str | None = None) -> None:
    """
    Set user context for error tracking.
    
    Args:
        user_id: User identifier
        email: User email
        role: User role
    """
    if not _sentry_available or _sentry_sdk is None:
        return
    
    _sentry_sdk.set_user({
        "id": user_id,
        "email": email,
        "role": role,
    })


def set_tenant_context(tenant_id: str, tenant_name: str | None = None) -> None:
    """
    Set tenant context as tags.
    
    Args:
        tenant_id: Tenant identifier
        tenant_name: Tenant name
    """
    if not _sentry_available or _sentry_sdk is None:
        return
    
    _sentry_sdk.set_tag("tenant.id", tenant_id)
    if tenant_name:
        _sentry_sdk.set_tag("tenant.name", tenant_name)


def add_breadcrumb(
    message: str,
    category: str = "action",
    level: str = "info",
    data: dict[str, Any] | None = None,
) -> None:
    """
    Add a breadcrumb for debugging context.
    
    Args:
        message: Breadcrumb message
        category: Category (e.g., 'http', 'query', 'action')
        level: Severity level
        data: Additional data
    """
    if not _sentry_available or _sentry_sdk is None:
        return
    
    _sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data,
    )


def capture_message(message: str, level: str = "info") -> str | None:
    """
    Capture a message to Sentry.
    
    Args:
        message: Message to capture
        level: Severity level (debug, info, warning, error, fatal)
        
    Returns:
        Event ID if captured, None otherwise
    """
    if not _sentry_available or _sentry_sdk is None:
        return None
    
    return _sentry_sdk.capture_message(message, level=level)


def capture_exception(exception: Exception | None = None) -> str | None:
    """
    Capture an exception to Sentry.
    
    Args:
        exception: Exception to capture (uses current if None)
        
    Returns:
        Event ID if captured, None otherwise
    """
    if not _sentry_available or _sentry_sdk is None:
        return None
    
    return _sentry_sdk.capture_exception(exception)


def set_tag(key: str, value: str) -> None:
    """Set a tag on the current scope."""
    if not _sentry_available or _sentry_sdk is None:
        return
    _sentry_sdk.set_tag(key, value)


def set_context(name: str, data: dict[str, Any]) -> None:
    """Set a context on the current scope."""
    if not _sentry_available or _sentry_sdk is None:
        return
    _sentry_sdk.set_context(name, data)
