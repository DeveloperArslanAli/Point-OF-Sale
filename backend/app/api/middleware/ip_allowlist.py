"""IP Allowlist middleware for restricting access to admin endpoints.

Provides IP-based access control for sensitive administrative operations.
Supports both IPv4 and IPv6 addresses, CIDR notation, and dynamic allowlists.
"""
from __future__ import annotations

import ipaddress
from typing import Callable, Sequence

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.settings import get_settings

logger = structlog.get_logger(__name__)


class IPAllowlistMiddleware(BaseHTTPMiddleware):
    """Middleware that restricts access to specified paths based on client IP.
    
    Features:
    - IPv4 and IPv6 support
    - CIDR notation (e.g., 192.168.1.0/24)
    - Per-path allowlists
    - Bypass for local/development environments
    - X-Forwarded-For header support for proxied requests
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        protected_paths: Sequence[str] | None = None,
        allowed_ips: Sequence[str] | None = None,
        trust_proxy_headers: bool = True,
        enabled: bool = True,
    ) -> None:
        """Initialize IP allowlist middleware.
        
        Args:
            app: ASGI application
            protected_paths: URL path prefixes to protect (e.g., ["/api/v1/admin"])
            allowed_ips: List of allowed IPs or CIDR ranges
            trust_proxy_headers: Whether to trust X-Forwarded-For headers
            enabled: Whether to enforce allowlist (can be disabled in dev)
        """
        super().__init__(app)
        self._enabled = enabled
        self._trust_proxy = trust_proxy_headers
        
        # Default protected paths - super admin and sensitive operations
        self._protected_paths = protected_paths or [
            "/api/v1/tenants",
            "/api/v1/admin",
            "/api/v1/super-admin",
        ]
        
        # Parse allowed IPs/networks
        self._allowed_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        self._parse_allowed_ips(allowed_ips or [])
        
        # Always allow localhost in any environment
        self._add_localhost_networks()

    def _parse_allowed_ips(self, ips: Sequence[str]) -> None:
        """Parse IP addresses and CIDR ranges into network objects."""
        for ip_str in ips:
            try:
                # Try parsing as network (CIDR notation)
                network = ipaddress.ip_network(ip_str, strict=False)
                self._allowed_networks.append(network)
                logger.debug("ip_allowlist_added", network=str(network))
            except ValueError as e:
                logger.warning(
                    "ip_allowlist_parse_error",
                    ip=ip_str,
                    error=str(e),
                )

    def _add_localhost_networks(self) -> None:
        """Add localhost networks to the allowlist."""
        localhost_networks = [
            "127.0.0.0/8",      # IPv4 localhost
            "::1/128",          # IPv6 localhost
            "10.0.0.0/8",       # Private network (Docker, etc.)
            "172.16.0.0/12",    # Private network
            "192.168.0.0/16",   # Private network
        ]
        for net_str in localhost_networks:
            try:
                network = ipaddress.ip_network(net_str, strict=False)
                self._allowed_networks.append(network)
            except ValueError:
                pass

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request.
        
        Handles proxied requests via X-Forwarded-For header.
        """
        if self._trust_proxy:
            # Check X-Forwarded-For header (set by reverse proxies)
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                # Take the first IP (original client)
                return forwarded_for.split(",")[0].strip()
            
            # Check X-Real-IP header (nginx)
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip.strip()
        
        # Fall back to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"

    def _is_ip_allowed(self, ip_str: str) -> bool:
        """Check if an IP address is in the allowlist."""
        try:
            ip = ipaddress.ip_address(ip_str)
            return any(ip in network for network in self._allowed_networks)
        except ValueError:
            logger.warning("ip_allowlist_invalid_ip", ip=ip_str)
            return False

    def _is_protected_path(self, path: str) -> bool:
        """Check if the request path requires IP allowlist check."""
        return any(path.startswith(prefix) for prefix in self._protected_paths)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process request and check IP allowlist for protected paths."""
        settings = get_settings()
        
        # Skip check if disabled or in development
        if not self._enabled or settings.ENV == "dev":
            return await call_next(request)
        
        # Only check protected paths
        if not self._is_protected_path(request.url.path):
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        
        if not self._is_ip_allowed(client_ip):
            logger.warning(
                "ip_allowlist_blocked",
                client_ip=client_ip,
                path=request.url.path,
                method=request.method,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Access denied: IP not in allowlist",
                    "code": "ip_not_allowed",
                },
            )
        
        logger.debug(
            "ip_allowlist_allowed",
            client_ip=client_ip,
            path=request.url.path,
        )
        
        return await call_next(request)


def create_ip_allowlist_middleware(
    app: ASGIApp,
    *,
    additional_ips: Sequence[str] | None = None,
    additional_paths: Sequence[str] | None = None,
) -> IPAllowlistMiddleware:
    """Create IP allowlist middleware with settings from environment.
    
    Reads allowed IPs from IP_ALLOWLIST setting (comma-separated).
    
    Args:
        app: ASGI application
        additional_ips: Additional IPs to allow beyond settings
        additional_paths: Additional paths to protect
        
    Returns:
        Configured IPAllowlistMiddleware
    """
    settings = get_settings()
    
    # Get IPs from settings
    allowed_ips = []
    if hasattr(settings, "IP_ALLOWLIST") and settings.IP_ALLOWLIST:
        allowed_ips.extend(
            ip.strip() 
            for ip in settings.IP_ALLOWLIST.split(",") 
            if ip.strip()
        )
    
    if additional_ips:
        allowed_ips.extend(additional_ips)
    
    # Get protected paths
    protected_paths = [
        "/api/v1/tenants",
        "/api/v1/admin",
        "/api/v1/super-admin",
    ]
    if additional_paths:
        protected_paths.extend(additional_paths)
    
    # Enable only in production/staging
    enabled = settings.ENV in ("staging", "prod")
    
    return IPAllowlistMiddleware(
        app,
        protected_paths=protected_paths,
        allowed_ips=allowed_ips,
        enabled=enabled,
    )
