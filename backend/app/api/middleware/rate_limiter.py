"""Rate limiting middleware using Redis for distributed rate limiting.

Implements sliding window rate limiting for:
- Login endpoints (strict limits to prevent brute force)
- General API endpoints (higher limits for normal operation)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.settings import get_settings

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class RateLimiter:
    """Sliding window rate limiter using Redis."""

    def __init__(
        self,
        redis_client: Any = None,
        default_limit: int = 100,
        default_window: int = 60,
    ) -> None:
        """Initialize rate limiter.

        Args:
            redis_client: Redis async client (optional, disabled if None)
            default_limit: Default number of requests allowed per window
            default_window: Default window size in seconds
        """
        self._redis: Any = redis_client
        self._default_limit = default_limit
        self._default_window = default_window

    @property
    def enabled(self) -> bool:
        """Check if rate limiting is enabled (Redis available)."""
        return self._redis is not None

    async def check_rate_limit(
        self,
        key: str,
        limit: int | None = None,
        window: int | None = None,
    ) -> tuple[bool, int, int]:
        """Check if request is within rate limit.

        Args:
            key: Unique identifier for the rate limit (e.g., "login:192.168.1.1")
            limit: Maximum requests allowed (uses default if None)
            window: Time window in seconds (uses default if None)

        Returns:
            Tuple of (allowed, remaining, retry_after)
            - allowed: Whether the request is allowed
            - remaining: Number of requests remaining
            - retry_after: Seconds to wait if blocked (0 if allowed)
        """
        if not self.enabled:
            return True, limit or self._default_limit, 0

        limit = limit or self._default_limit
        window = window or self._default_window
        now = time.time()
        window_start = now - window

        try:
            # Use Redis sorted set for sliding window
            pipe = self._redis.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request with timestamp as score
            pipe.zadd(key, {f"{now}:{id(key)}": now})
            
            # Set expiry on the key
            pipe.expire(key, window + 1)
            
            results = await pipe.execute()
            current_count = results[1]  # zcard result

            if current_count >= limit:
                # Calculate retry_after based on oldest entry
                oldest = await self._redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_time = oldest[0][1]
                    retry_after = int(oldest_time + window - now) + 1
                else:
                    retry_after = window
                return False, 0, max(1, retry_after)

            remaining = limit - current_count - 1
            return True, max(0, remaining), 0

        except Exception as exc:
            # Log error but allow request on Redis failure (fail-open)
            logger.warning(
                "rate_limit_check_failed",
                key=key,
                error=str(exc),
            )
            return True, limit, 0


# Route-specific rate limit configurations
RATE_LIMIT_CONFIG: dict[str, dict[str, int]] = {
    # Auth endpoints - strict limits to prevent brute force
    "/api/v1/auth/login": {"limit": 5, "window": 60},  # 5 attempts per minute
    "/api/v1/auth/register": {"limit": 3, "window": 60},  # 3 registrations per minute
    "/api/v1/auth/refresh": {"limit": 10, "window": 60},  # 10 refresh per minute
    "/api/v1/auth/forgot-password": {"limit": 3, "window": 300},  # 3 per 5 minutes
    
    # Payment endpoints - moderate limits
    "/api/v1/payments": {"limit": 30, "window": 60},  # 30 per minute
    
    # Report endpoints - can be expensive
    "/api/v1/reports": {"limit": 20, "window": 60},  # 20 per minute
}


def get_rate_limit_key(request: Request) -> str:
    """Generate rate limit key based on client IP and path.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Rate limit key string
    """
    # Get client IP (considering X-Forwarded-For for reverse proxies)
    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.client.host if request.client else "unknown"
    
    # Normalize path (remove query params, trailing slashes)
    path = request.url.path.rstrip("/")
    
    return f"rate_limit:{path}:{client_ip}"


def get_config_for_path(path: str) -> dict[str, int]:
    """Get rate limit config for a path.
    
    Matches path prefixes to allow configuration for path patterns.
    
    Args:
        path: Request path
        
    Returns:
        Rate limit configuration dict with 'limit' and 'window' keys
    """
    path = path.rstrip("/")
    
    # Exact match first
    if path in RATE_LIMIT_CONFIG:
        return RATE_LIMIT_CONFIG[path]
    
    # Prefix match for pattern support (e.g., /api/v1/reports/*)
    for pattern, config in RATE_LIMIT_CONFIG.items():
        if path.startswith(pattern):
            return config
    
    # Default: 100 requests per minute
    return {"limit": 100, "window": 60}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis sliding window.
    
    Supports two modes:
    1. Pass rate_limiter directly at init time
    2. Lazy initialization from app.state.rate_limiter (for async lifespan setup)
    """

    def __init__(
        self,
        app: ASGIApp,
        rate_limiter: RateLimiter | None = None,
        skip_paths: list[str] | None = None,
    ) -> None:
        """Initialize rate limit middleware.
        
        Args:
            app: ASGI application
            rate_limiter: RateLimiter instance (if None, uses app.state.rate_limiter)
            skip_paths: Paths to skip rate limiting (e.g., /health)
        """
        super().__init__(app)
        self._rate_limiter = rate_limiter
        self._skip_paths = set(skip_paths or ["/health", "/docs", "/openapi.json", "/redoc", "/metrics"])

    def _get_rate_limiter(self, request: Request) -> RateLimiter:
        """Get rate limiter, falling back to app.state if not set."""
        if self._rate_limiter is not None:
            return self._rate_limiter
        # Lazy load from app.state (set in lifespan)
        return getattr(request.app.state, "rate_limiter", None) or RateLimiter()

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process request with rate limiting."""
        path = request.url.path.rstrip("/")
        rate_limiter = self._get_rate_limiter(request)
        
        # Skip rate limiting for certain paths
        if path in self._skip_paths or not rate_limiter.enabled:
            return await call_next(request)

        key = get_rate_limit_key(request)
        config = get_config_for_path(path)
        
        allowed, remaining, retry_after = await rate_limiter.check_rate_limit(
            key=key,
            limit=config["limit"],
            window=config["window"],
        )

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                path=path,
                key=key,
                retry_after=retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "code": "rate_limit.exceeded",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(config["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(retry_after),
                },
            )

        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(config["limit"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response


# Factory function to create middleware with Redis
async def create_rate_limiter_with_redis(redis_url: str | None = None) -> RateLimiter:
    """Create a rate limiter with Redis connection.
    
    Args:
        redis_url: Redis connection URL (uses settings if None)
        
    Returns:
        RateLimiter instance (disabled if Redis unavailable)
    """
    settings = get_settings()
    url = redis_url or settings.REDIS_URL

    # Allow disabling Redis entirely
    if not url:
        logger.warning("rate_limiter_disabled", reason="redis_url_missing")
        return RateLimiter(redis_client=None)
    
    try:
        import redis.asyncio as aioredis
        
        client = aioredis.from_url(url, decode_responses=True)
        # Test connection
        await client.ping()
        logger.info("rate_limiter_enabled", redis_url=url)
        return RateLimiter(redis_client=client)
    except Exception as exc:
        logger.warning(
            "rate_limiter_disabled",
            reason="redis_unavailable",
            error=str(exc),
        )
        return RateLimiter(redis_client=None)
