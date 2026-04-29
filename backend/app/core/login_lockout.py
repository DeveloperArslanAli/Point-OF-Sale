"""Login lockout service for brute-force attack protection.

This module tracks failed login attempts and temporarily locks accounts
after too many failures. Uses Redis for distributed tracking.

Usage:
    from app.core.login_lockout import LoginLockoutService
    
    lockout = LoginLockoutService(redis_client)
    
    # Before authenticating
    if await lockout.is_locked(email):
        raise AuthenticationError("Account temporarily locked")
    
    # After failed login
    await lockout.record_failure(email)
    
    # After successful login
    await lockout.clear_failures(email)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.core.settings import get_settings

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = structlog.get_logger()


class LoginLockoutService:
    """Service for managing account lockouts after failed login attempts.
    
    Default policy:
    - Lock after 5 failed attempts
    - Lock duration: 15 minutes
    - Tracks attempts in sliding window of 30 minutes
    """
    
    DEFAULT_MAX_ATTEMPTS = 5
    DEFAULT_LOCKOUT_SECONDS = 15 * 60  # 15 minutes
    DEFAULT_WINDOW_SECONDS = 30 * 60   # 30 minutes
    KEY_PREFIX = "login:failures:"
    LOCK_PREFIX = "login:locked:"
    
    def __init__(
        self,
        redis_client: "Redis | None" = None,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        lockout_seconds: int = DEFAULT_LOCKOUT_SECONDS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._max_attempts = max_attempts
        self._lockout_seconds = lockout_seconds
        self._window_seconds = window_seconds

    @property
    def enabled(self) -> bool:
        """Check if lockout is enabled (requires Redis)."""
        return self._redis is not None

    def _failure_key(self, identifier: str) -> str:
        """Get Redis key for failure count."""
        return f"{self.KEY_PREFIX}{identifier.lower()}"

    def _lock_key(self, identifier: str) -> str:
        """Get Redis key for lock status."""
        return f"{self.LOCK_PREFIX}{identifier.lower()}"

    async def is_locked(self, identifier: str) -> bool:
        """Check if an identifier (email/IP) is currently locked.
        
        Args:
            identifier: Email address or IP to check
            
        Returns:
            True if locked, False otherwise
        """
        if not self.enabled:
            return False
            
        try:
            lock_key = self._lock_key(identifier)
            return await self._redis.exists(lock_key) > 0  # type: ignore
        except Exception as e:
            logger.warning("lockout_check_failed", error=str(e))
            return False  # Fail open

    async def get_lockout_remaining(self, identifier: str) -> int | None:
        """Get remaining lockout time in seconds.
        
        Args:
            identifier: Email address or IP to check
            
        Returns:
            Remaining seconds, or None if not locked
        """
        if not self.enabled:
            return None
            
        try:
            lock_key = self._lock_key(identifier)
            ttl = await self._redis.ttl(lock_key)  # type: ignore
            return ttl if ttl > 0 else None
        except Exception as e:
            logger.warning("lockout_ttl_check_failed", error=str(e))
            return None

    async def get_failure_count(self, identifier: str) -> int:
        """Get current failure count for identifier.
        
        Args:
            identifier: Email address or IP to check
            
        Returns:
            Number of failed attempts in current window
        """
        if not self.enabled:
            return 0
            
        try:
            failure_key = self._failure_key(identifier)
            count = await self._redis.get(failure_key)  # type: ignore
            return int(count) if count else 0
        except Exception as e:
            logger.warning("failure_count_check_failed", error=str(e))
            return 0

    async def record_failure(self, identifier: str, ip_address: str | None = None) -> bool:
        """Record a failed login attempt.
        
        Args:
            identifier: Email address that failed
            ip_address: Optional IP to also track
            
        Returns:
            True if account is now locked
        """
        if not self.enabled:
            return False
            
        try:
            failure_key = self._failure_key(identifier)
            
            # Increment failure count
            pipe = self._redis.pipeline()  # type: ignore
            pipe.incr(failure_key)
            pipe.expire(failure_key, self._window_seconds)
            results = await pipe.execute()
            
            count = results[0]
            
            # Also track by IP if provided
            if ip_address:
                ip_key = self._failure_key(f"ip:{ip_address}")
                await self._redis.incr(ip_key)  # type: ignore
                await self._redis.expire(ip_key, self._window_seconds)  # type: ignore
            
            logger.info(
                "login_failure_recorded",
                identifier=identifier,
                attempt_count=count,
                max_attempts=self._max_attempts,
            )
            
            # Lock if exceeded threshold
            if count >= self._max_attempts:
                lock_key = self._lock_key(identifier)
                await self._redis.set(  # type: ignore
                    lock_key,
                    "1",
                    ex=self._lockout_seconds,
                )
                logger.warning(
                    "account_locked",
                    identifier=identifier,
                    lockout_seconds=self._lockout_seconds,
                )
                return True
            
            return False
            
        except Exception as e:
            logger.warning("record_failure_failed", error=str(e))
            return False

    async def clear_failures(self, identifier: str) -> None:
        """Clear failure count after successful login.
        
        Args:
            identifier: Email address that logged in successfully
        """
        if not self.enabled:
            return
            
        try:
            failure_key = self._failure_key(identifier)
            await self._redis.delete(failure_key)  # type: ignore
            logger.info("login_failures_cleared", identifier=identifier)
        except Exception as e:
            logger.warning("clear_failures_failed", error=str(e))

    async def unlock(self, identifier: str) -> None:
        """Manually unlock an account (admin action).
        
        Args:
            identifier: Email address to unlock
        """
        if not self.enabled:
            return
            
        try:
            lock_key = self._lock_key(identifier)
            failure_key = self._failure_key(identifier)
            await self._redis.delete(lock_key, failure_key)  # type: ignore
            logger.info("account_unlocked", identifier=identifier)
        except Exception as e:
            logger.warning("unlock_failed", error=str(e))


# Factory function
async def create_login_lockout_service(
    redis_url: str | None = None,
) -> LoginLockoutService:
    """Create a login lockout service with Redis connection.
    
    Args:
        redis_url: Redis connection URL (uses settings if None)
        
    Returns:
        LoginLockoutService instance (disabled if Redis unavailable)
    """
    settings = get_settings()
    url = redis_url or settings.REDIS_URL
    
    if not url:
        logger.warning("login_lockout_disabled", reason="no_redis_url")
        return LoginLockoutService(redis_client=None)
    
    try:
        import redis.asyncio as aioredis
        
        client = aioredis.from_url(url, decode_responses=True)
        await client.ping()
        logger.info("login_lockout_enabled", redis_url=url)
        return LoginLockoutService(redis_client=client)
    except Exception as e:
        logger.warning(
            "login_lockout_disabled",
            reason="redis_unavailable",
            error=str(e),
        )
        return LoginLockoutService(redis_client=None)
