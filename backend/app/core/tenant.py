"""
Tenant isolation middleware and context management.

Provides multi-tenant data isolation by:
1. Extracting tenant_id from JWT tokens
2. Setting tenant context for the request lifetime
3. Providing utilities for accessing current tenant context

Usage:
    # In FastAPI app setup
    app.add_middleware(TenantContextMiddleware)
    
    # In repository or service code
    from app.core.tenant import get_current_tenant_id
    
    tenant_id = get_current_tenant_id()
    if tenant_id:
        query = query.where(Model.tenant_id == tenant_id)
"""

from __future__ import annotations

import contextvars
from typing import Any, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.settings import get_settings
from app.infrastructure.auth.token_provider import TokenProvider

logger = structlog.get_logger(__name__)

# Context variable for tenant ID - thread/coroutine safe
_tenant_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tenant_id", default=None
)

# Context variable for user ID
_user_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "user_id", default=None
)


def get_current_tenant_id() -> str | None:
    """
    Get the current tenant ID from context.
    
    Returns None if no tenant context is set (e.g., for public endpoints).
    """
    return _tenant_context.get()


def get_current_user_id() -> str | None:
    """
    Get the current user ID from context.
    
    Returns None if no user context is set (e.g., for public endpoints).
    """
    return _user_context.get()


def set_tenant_context(tenant_id: str | None) -> contextvars.Token[str | None]:
    """
    Set the tenant context for the current execution context.
    
    Returns a token that can be used to reset the context.
    """
    return _tenant_context.set(tenant_id)


def reset_tenant_context(token: contextvars.Token[str | None]) -> None:
    """Reset tenant context to its previous value."""
    _tenant_context.reset(token)


def set_user_context(user_id: str | None) -> contextvars.Token[str | None]:
    """Set the user context for the current execution context."""
    return _user_context.set(user_id)


def reset_user_context(token: contextvars.Token[str | None]) -> None:
    """Reset user context to its previous value."""
    _user_context.reset(token)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts tenant_id from JWT and sets context.
    
    This middleware:
    1. Extracts the Authorization header
    2. Decodes the JWT token
    3. Sets tenant_id and user_id in context variables
    4. Cleans up context after request completion
    
    Endpoints without valid tokens will have tenant_id = None,
    which allows public endpoints to work without tenant context.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        tenant_token: contextvars.Token[str | None] | None = None
        user_token: contextvars.Token[str | None] | None = None
        
        try:
            # Extract tenant from Authorization header
            auth_header = request.headers.get("Authorization", "")
            
            if auth_header.startswith("Bearer "):
                token_str = auth_header[7:]  # Remove "Bearer " prefix
                
                try:
                    settings = get_settings()
                    provider = TokenProvider(
                        secret=settings.JWT_SECRET_KEY,
                        issuer=getattr(settings, "JWT_ISSUER", "pos-backend"),
                    )
                    payload = provider.decode_token(token_str)
                    
                    # Extract tenant_id and user_id from JWT payload
                    tenant_id = payload.get("tenant_id")
                    user_id = payload.get("sub")
                    
                    if tenant_id:
                        tenant_token = set_tenant_context(tenant_id)
                        logger.debug(
                            "tenant_context_set",
                            tenant_id=tenant_id,
                            path=request.url.path,
                        )
                    
                    if user_id:
                        user_token = set_user_context(user_id)
                        
                except Exception as e:
                    # Token decode failed - continue without tenant context
                    logger.debug(
                        "tenant_extraction_failed",
                        error=str(e),
                        path=request.url.path,
                    )
            
            # Process the request
            response = await call_next(request)
            
            return response
            
        finally:
            # Always clean up context
            if tenant_token:
                reset_tenant_context(tenant_token)
            if user_token:
                reset_user_context(user_token)


def require_tenant() -> Callable[[], str]:
    """
    FastAPI dependency that requires a valid tenant context.
    
    Usage:
        @router.get("/items")
        async def list_items(tenant_id: str = Depends(require_tenant())):
            ...
    """
    def dependency() -> str:
        from app.domain.common.errors import UnauthorizedError
        
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            raise UnauthorizedError("Tenant context required")
        return tenant_id
    
    return dependency


class TenantAwareRepository:
    """
    Base class for repositories that should filter by tenant.
    
    Provides automatic tenant filtering when a tenant context is set.
    
    Usage:
        class MyRepository(TenantAwareRepository):
            async def get_all(self) -> list[MyEntity]:
                query = select(MyModel)
                query = self._apply_tenant_filter(query, MyModel)
                ...
    """
    
    def _apply_tenant_filter(self, query, model_class):
        """
        Apply tenant filter to a query if tenant context is set.
        
        Args:
            query: SQLAlchemy query object
            model_class: The SQLAlchemy model class (must have tenant_id column)
            
        Returns:
            Query with tenant filter applied if tenant context exists
        """
        tenant_id = get_current_tenant_id()
        
        if tenant_id and hasattr(model_class, "tenant_id"):
            query = query.where(model_class.tenant_id == tenant_id)
        
        return query
    
    def _get_tenant_id(self) -> str | None:
        """Get the current tenant ID from context."""
        return get_current_tenant_id()
