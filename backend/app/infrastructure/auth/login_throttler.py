"""Login throttling and account lockout service.

Implements brute-force protection:
- Tracks failed login attempts per email/IP
- Locks accounts after N consecutive failures
- Implements progressive delays
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any

import structlog

from app.core.settings import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class LockoutStatus:
    """Current lockout status for an account."""
    
    is_locked: bool
    failed_attempts: int
    lockout_remaining_seconds: int
    next_attempt_delay: int  # Progressive delay in seconds


class LoginThrottler:
    """Tracks and enforces login attempt limits.
    
    Uses Redis for distributed tracking with the following keys:
    - login_attempts:{identifier}: Counter of failed attempts
    - login_lockout:{identifier}: Lockout timestamp
    """
    
    # Configuration
    MAX_ATTEMPTS: int = 5  # Lock after this many failures
    LOCKOUT_DURATION_SECONDS: int = 900  # 15 minutes lockout
    ATTEMPT_WINDOW_SECONDS: int = 300  # 5 minute window for counting attempts
    PROGRESSIVE_DELAYS: list[int] = [0, 0, 1, 2, 5, 10]  # Delay per attempt number
    
    def __init__(self, redis_client: Any = None) -> None:
        """Initialize login throttler.
        
        Args:
            redis_client: Redis async client (disabled if None)
        """
        self._redis: Any = redis_client
    
    @property
    def enabled(self) -> bool:
        """Check if throttling is enabled (Redis available)."""
        return self._redis is not None
    
    def _hash_identifier(self, identifier: str) -> str:
        """Hash identifier for privacy in Redis keys.
        
        Args:
            identifier: Email or IP address
            
        Returns:
            Hashed identifier
        """
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]
    
    def _get_keys(self, identifier: str) -> tuple[str, str]:
        """Get Redis keys for an identifier.
        
        Args:
            identifier: Email or IP address
            
        Returns:
            Tuple of (attempts_key, lockout_key)
        """
        hashed = self._hash_identifier(identifier)
        return (
            f"login_attempts:{hashed}",
            f"login_lockout:{hashed}",
        )
    
    async def check_lockout(self, email: str, ip_address: str | None = None) -> LockoutStatus:
        """Check if login is allowed for an identifier.
        
        Args:
            email: User email attempting login
            ip_address: Optional client IP address
            
        Returns:
            LockoutStatus with current state
        """
        if not self.enabled:
            return LockoutStatus(
                is_locked=False,
                failed_attempts=0,
                lockout_remaining_seconds=0,
                next_attempt_delay=0,
            )
        
        # Check both email and IP-based lockouts
        identifiers = [email]
        if ip_address:
            identifiers.append(ip_address)
        
        max_attempts = 0
        is_locked = False
        lockout_remaining = 0
        
        try:
            for identifier in identifiers:
                attempts_key, lockout_key = self._get_keys(identifier)
                
                # Check lockout
                lockout_until = await self._redis.get(lockout_key)
                if lockout_until:
                    remaining = float(lockout_until) - time.time()
                    if remaining > 0:
                        is_locked = True
                        lockout_remaining = max(lockout_remaining, int(remaining))
                        continue
                
                # Get attempt count
                attempts = await self._redis.get(attempts_key)
                if attempts:
                    max_attempts = max(max_attempts, int(attempts))
            
            # Calculate progressive delay
            delay_index = min(max_attempts, len(self.PROGRESSIVE_DELAYS) - 1)
            next_delay = self.PROGRESSIVE_DELAYS[delay_index]
            
            return LockoutStatus(
                is_locked=is_locked,
                failed_attempts=max_attempts,
                lockout_remaining_seconds=lockout_remaining,
                next_attempt_delay=next_delay,
            )
            
        except Exception as exc:
            logger.warning(
                "lockout_check_failed",
                email=email[:3] + "***",  # Partial email for logging
                error=str(exc),
            )
            # Fail open on Redis errors
            return LockoutStatus(
                is_locked=False,
                failed_attempts=0,
                lockout_remaining_seconds=0,
                next_attempt_delay=0,
            )
    
    async def record_failed_attempt(
        self,
        email: str,
        ip_address: str | None = None,
    ) -> LockoutStatus:
        """Record a failed login attempt.
        
        Args:
            email: User email that failed login
            ip_address: Optional client IP address
            
        Returns:
            Updated LockoutStatus
        """
        if not self.enabled:
            return LockoutStatus(
                is_locked=False,
                failed_attempts=0,
                lockout_remaining_seconds=0,
                next_attempt_delay=0,
            )
        
        identifiers = [email]
        if ip_address:
            identifiers.append(ip_address)
        
        max_attempts = 0
        
        try:
            for identifier in identifiers:
                attempts_key, lockout_key = self._get_keys(identifier)
                
                # Increment attempt counter
                pipe = self._redis.pipeline()
                pipe.incr(attempts_key)
                pipe.expire(attempts_key, self.ATTEMPT_WINDOW_SECONDS)
                results = await pipe.execute()
                
                attempts = results[0]
                max_attempts = max(max_attempts, attempts)
                
                # Check if we should lock
                if attempts >= self.MAX_ATTEMPTS:
                    lockout_until = time.time() + self.LOCKOUT_DURATION_SECONDS
                    await self._redis.setex(
                        lockout_key,
                        self.LOCKOUT_DURATION_SECONDS,
                        str(lockout_until),
                    )
                    logger.warning(
                        "account_locked",
                        identifier_hash=self._hash_identifier(identifier),
                        attempts=attempts,
                        lockout_seconds=self.LOCKOUT_DURATION_SECONDS,
                    )
            
            is_locked = max_attempts >= self.MAX_ATTEMPTS
            lockout_remaining = self.LOCKOUT_DURATION_SECONDS if is_locked else 0
            delay_index = min(max_attempts, len(self.PROGRESSIVE_DELAYS) - 1)
            
            return LockoutStatus(
                is_locked=is_locked,
                failed_attempts=max_attempts,
                lockout_remaining_seconds=lockout_remaining,
                next_attempt_delay=self.PROGRESSIVE_DELAYS[delay_index],
            )
            
        except Exception as exc:
            logger.warning(
                "record_failed_attempt_error",
                email=email[:3] + "***",
                error=str(exc),
            )
            return LockoutStatus(
                is_locked=False,
                failed_attempts=0,
                lockout_remaining_seconds=0,
                next_attempt_delay=0,
            )
    
    async def record_successful_login(
        self,
        email: str,
        ip_address: str | None = None,
    ) -> None:
        """Clear failed attempts after successful login.
        
        Args:
            email: User email that logged in successfully
            ip_address: Optional client IP address
        """
        if not self.enabled:
            return
        
        identifiers = [email]
        if ip_address:
            identifiers.append(ip_address)
        
        try:
            for identifier in identifiers:
                attempts_key, lockout_key = self._get_keys(identifier)
                await self._redis.delete(attempts_key, lockout_key)
                
        except Exception as exc:
            logger.warning(
                "clear_attempts_error",
                error=str(exc),
            )
    
    async def unlock_account(self, email: str) -> bool:
        """Manually unlock an account (admin action).
        
        Args:
            email: Email to unlock
            
        Returns:
            True if unlocked, False on error
        """
        if not self.enabled:
            return True
        
        try:
            attempts_key, lockout_key = self._get_keys(email)
            await self._redis.delete(attempts_key, lockout_key)
            logger.info(
                "account_unlocked",
                email_hash=self._hash_identifier(email),
            )
            return True
        except Exception as exc:
            logger.error(
                "unlock_account_error",
                error=str(exc),
            )
            return False


# Global instance (initialized on app startup)
_login_throttler: LoginThrottler | None = None


async def get_login_throttler() -> LoginThrottler:
    """Get or create the login throttler instance.
    
    Returns:
        LoginThrottler instance
    """
    global _login_throttler
    
    if _login_throttler is None:
        settings = get_settings()
        try:
            import redis.asyncio as aioredis
            
            client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await client.ping()
            _login_throttler = LoginThrottler(redis_client=client)
            logger.info("login_throttler_enabled")
        except Exception as exc:
            logger.warning(
                "login_throttler_disabled",
                reason="redis_unavailable",
                error=str(exc),
            )
            _login_throttler = LoginThrottler(redis_client=None)
    
    return _login_throttler


def set_login_throttler(throttler: LoginThrottler) -> None:
    """Set the global login throttler (for testing).
    
    Args:
        throttler: LoginThrottler instance to use
    """
    global _login_throttler
    _login_throttler = throttler
