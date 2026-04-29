"""Security headers middleware.

Adds security headers to all responses:
- Content-Security-Policy (CSP)
- Strict-Transport-Security (HSTS)
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection
- Referrer-Policy
- Permissions-Policy
"""

from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from app.core.settings import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all responses."""

    def __init__(
        self,
        app: ASGIApp,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1 year
        enable_csp: bool = True,
        csp_policy: str | None = None,
        frame_options: str = "DENY",
    ) -> None:
        """Initialize security headers middleware.
        
        Args:
            app: ASGI application
            enable_hsts: Whether to enable HSTS header
            hsts_max_age: HSTS max-age in seconds (default: 1 year)
            enable_csp: Whether to enable Content-Security-Policy
            csp_policy: Custom CSP policy (uses default if None)
            frame_options: X-Frame-Options value (DENY, SAMEORIGIN, or ALLOW-FROM uri)
        """
        super().__init__(app)
        self._enable_hsts = enable_hsts
        self._hsts_max_age = hsts_max_age
        self._enable_csp = enable_csp
        self._frame_options = frame_options
        
        # Default CSP for API backend - restrictive
        self._csp_policy = csp_policy or "; ".join([
            "default-src 'none'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",  # For Swagger UI
            "img-src 'self' data: https:",
            "font-src 'self'",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ])

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process request and add security headers to response."""
        response = await call_next(request)
        
        settings = get_settings()
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Clickjacking protection
        response.headers["X-Frame-Options"] = self._frame_options
        
        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Restrict browser features
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        
        # HSTS - only in production over HTTPS
        if self._enable_hsts and settings.ENV in ("staging", "prod"):
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self._hsts_max_age}; includeSubDomains; preload"
            )
        
        # Content Security Policy
        if self._enable_csp:
            # Use report-only in dev for debugging
            header_name = (
                "Content-Security-Policy-Report-Only"
                if settings.ENV == "dev"
                else "Content-Security-Policy"
            )
            response.headers[header_name] = self._csp_policy
        
        # Prevent caching of sensitive responses
        if self._is_sensitive_endpoint(request.url.path):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response

    def _is_sensitive_endpoint(self, path: str) -> bool:
        """Check if endpoint handles sensitive data.
        
        Args:
            path: Request path
            
        Returns:
            True if endpoint is sensitive
        """
        sensitive_prefixes = (
            "/api/v1/auth",
            "/api/v1/payments",
            "/api/v1/customers",
            "/api/v1/employees",
            "/api/v1/reports",
        )
        return any(path.startswith(prefix) for prefix in sensitive_prefixes)


# Pre-configured instances for common use cases
def create_api_security_middleware(app: ASGIApp) -> SecurityHeadersMiddleware:
    """Create security middleware configured for API backend.
    
    Args:
        app: ASGI application
        
    Returns:
        Configured SecurityHeadersMiddleware
    """
    return SecurityHeadersMiddleware(
        app,
        enable_hsts=True,
        enable_csp=True,
        frame_options="DENY",
    )


def create_relaxed_security_middleware(app: ASGIApp) -> SecurityHeadersMiddleware:
    """Create security middleware with relaxed settings for development.
    
    Args:
        app: ASGI application
        
    Returns:
        Configured SecurityHeadersMiddleware with relaxed settings
    """
    return SecurityHeadersMiddleware(
        app,
        enable_hsts=False,
        enable_csp=False,  # Disabled to avoid breaking dev tools
        frame_options="SAMEORIGIN",
    )
