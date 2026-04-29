"""API Key authentication dependency."""
from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import structlog
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import set_tenant_context
from app.domain.api_keys.entities import ApiKey, ApiKeyScope
from app.infrastructure.db.repositories.api_key_repository import ApiKeyRepository
from app.infrastructure.db.session import get_session

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)
_hasher = PasswordHasher()

# API Key format: pos_live_XXXXXXXX.YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY
# prefix (pos_live_) + key_prefix (8 chars) + . + secret (32 chars)


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.
    
    Returns:
        Tuple of (full_key, key_prefix, key_hash)
    """
    key_prefix = secrets.token_hex(4)  # 8 chars
    key_secret = secrets.token_urlsafe(24)  # ~32 chars
    full_key = f"pos_live_{key_prefix}.{key_secret}"
    key_hash = _hasher.hash(full_key)
    return full_key, key_prefix, key_hash


def verify_api_key(full_key: str, key_hash: str) -> bool:
    """Verify an API key against its hash."""
    try:
        _hasher.verify(key_hash, full_key)
        return True
    except VerifyMismatchError:
        return False


async def get_api_key_from_request(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ApiKey | None:
    """
    Extract and validate API key from request headers.
    
    Looks for X-API-Key header or Authorization: Bearer pos_live_... header.
    Returns None if no API key found (allows fallback to JWT auth).
    """
    api_key_header = request.headers.get("X-API-Key")
    
    if not api_key_header:
        # Check Authorization header for API key format
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer pos_live_"):
            api_key_header = auth_header[7:]  # Remove "Bearer "
    
    if not api_key_header or not api_key_header.startswith("pos_live_"):
        return None
    
    try:
        # Parse key: pos_live_XXXXXXXX.SECRET
        parts = api_key_header[9:].split(".", 1)  # Remove pos_live_
        if len(parts) != 2:
            return None
        
        key_prefix = parts[0]
        
        # Look up key by prefix
        repo = ApiKeyRepository(session)
        api_key = await repo.get_by_prefix(key_prefix)
        
        if not api_key:
            logger.warning("api_key_not_found", key_prefix=key_prefix)
            return None
        
        # Verify the full key
        if not verify_api_key(api_key_header, api_key.key_hash):
            logger.warning("api_key_invalid", key_prefix=key_prefix)
            return None
        
        # Check if key is valid
        if not api_key.is_valid():
            logger.warning(
                "api_key_not_valid",
                key_prefix=key_prefix,
                status=api_key.status.value,
            )
            return None
        
        # Set tenant context from API key
        set_tenant_context(api_key.tenant_id)
        
        # Record usage (fire and forget)
        await repo.record_usage(api_key.id)
        
        logger.debug(
            "api_key_authenticated",
            key_prefix=key_prefix,
            tenant_id=api_key.tenant_id,
        )
        
        return api_key
        
    except Exception as e:
        logger.error("api_key_validation_error", error=str(e))
        return None


def require_api_key_scope(required_scope: str):
    """
    Dependency that requires a valid API key with specific scope.
    
    Usage:
        @router.get("/products")
        async def list_products(
            api_key: ApiKey = Depends(require_api_key_scope("read:products"))
        ):
            ...
    """
    async def dependency(
        request: Request,
        session: AsyncSession = Depends(get_session),
    ) -> ApiKey:
        api_key = await get_api_key_from_request(request, session)
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required",
                headers={"WWW-Authenticate": "X-API-Key"},
            )
        
        if not api_key.has_scope(required_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required scope: {required_scope}",
            )
        
        return api_key
    
    return dependency


class ApiKeyRateLimiter:
    """Rate limiter that uses API key's configured limit."""
    
    def __init__(self, redis_client=None):
        self._redis = redis_client
    
    async def check_rate_limit(self, api_key: ApiKey) -> tuple[bool, int]:
        """
        Check if API key is within rate limit.
        
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        if not self._redis:
            return True, api_key.rate_limit_per_minute
        
        key = f"api_key_rate:{api_key.id}"
        
        try:
            current = await self._redis.incr(key)
            
            if current == 1:
                await self._redis.expire(key, 60)
            
            remaining = max(0, api_key.rate_limit_per_minute - current)
            allowed = current <= api_key.rate_limit_per_minute
            
            return allowed, remaining
            
        except Exception as e:
            logger.error("api_key_rate_limit_error", error=str(e))
            return True, api_key.rate_limit_per_minute
