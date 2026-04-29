"""API Keys management router."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.api_key_auth import generate_api_key
from app.api.dependencies.auth import get_current_user, require_roles, ADMIN_ROLE
from app.core.tenant import get_current_tenant_id
from app.domain.api_keys.entities import ApiKey, ApiKeyScope, ApiKeyStatus
from app.domain.auth.entities import User
from app.infrastructure.db.repositories.api_key_repository import ApiKeyRepository
from app.infrastructure.db.session import get_session
from app.shared.pagination import PageParams

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


# Request/Response schemas
class CreateApiKeyRequest(BaseModel):
    """Request to create a new API key."""
    
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    """API Key response (without secret)."""
    
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    rate_limit_per_minute: int
    status: str
    created_by: str
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None


class ApiKeyCreatedResponse(BaseModel):
    """Response when API key is created (includes full key once)."""
    
    id: str
    name: str
    key_prefix: str
    api_key: str  # Full key - only shown once!
    scopes: list[str]
    rate_limit_per_minute: int
    status: str
    created_at: datetime
    expires_at: datetime | None
    warning: str = "Save this API key securely. It will not be shown again."


class ApiKeyListResponse(BaseModel):
    """Paginated list of API keys."""
    
    items: list[ApiKeyResponse]
    total: int
    page: int
    page_size: int


@router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    request: CreateApiKeyRequest,
    current_user: Annotated[User, Depends(require_roles(*ADMIN_ROLE))],
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new API key.
    
    The full API key is only returned once. Store it securely.
    
    Available scopes:
    - read:products, write:products
    - read:inventory, write:inventory
    - read:sales, write:sales
    - read:customers, write:customers
    - read:reports
    - webhooks
    - full_access
    """
    # Validate scopes
    valid_scopes = {s.value for s in ApiKeyScope}
    for scope in request.scopes:
        if scope not in valid_scopes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scope: {scope}. Valid scopes: {sorted(valid_scopes)}",
            )
    
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )
    
    # Generate the key
    full_key, key_prefix, key_hash = generate_api_key()
    
    api_key = ApiKey(
        tenant_id=tenant_id,
        name=request.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=request.scopes if request.scopes else [ApiKeyScope.READ_PRODUCTS.value],
        rate_limit_per_minute=request.rate_limit_per_minute,
        created_by=current_user.id,
        expires_at=request.expires_at,
    )
    
    repo = ApiKeyRepository(session)
    await repo.add(api_key)
    await session.commit()
    
    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        api_key=full_key,
        scopes=api_key.scopes,
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        status=api_key.status.value,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    current_user: Annotated[User, Depends(require_roles(*ADMIN_ROLE))],
    session: AsyncSession = Depends(get_session),
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
):
    """List all API keys for the current tenant."""
    repo = ApiKeyRepository(session)
    
    status_enum = None
    if status_filter:
        try:
            status_enum = ApiKeyStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )
    
    offset = (page - 1) * page_size
    keys, total = await repo.list_keys(
        status=status_enum,
        offset=offset,
        limit=page_size,
    )
    
    return ApiKeyListResponse(
        items=[
            ApiKeyResponse(
                id=k.id,
                name=k.name,
                key_prefix=k.key_prefix,
                scopes=k.scopes,
                rate_limit_per_minute=k.rate_limit_per_minute,
                status=k.status.value,
                created_by=k.created_by,
                created_at=k.created_at,
                last_used_at=k.last_used_at,
                expires_at=k.expires_at,
            )
            for k in keys
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    key_id: str,
    current_user: Annotated[User, Depends(require_roles(*ADMIN_ROLE))],
    session: AsyncSession = Depends(get_session),
):
    """Get API key details by ID."""
    repo = ApiKeyRepository(session)
    api_key = await repo.get_by_id(key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        status=api_key.status.value,
        created_by=api_key.created_by,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str,
    current_user: Annotated[User, Depends(require_roles(*ADMIN_ROLE))],
    session: AsyncSession = Depends(get_session),
):
    """Revoke an API key."""
    repo = ApiKeyRepository(session)
    api_key = await repo.get_by_id(key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    
    if api_key.status == ApiKeyStatus.REVOKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key already revoked",
        )
    
    api_key.revoke(current_user.id)
    await repo.update(api_key)
    await session.commit()


@router.get("/scopes/available", response_model=list[str])
async def list_available_scopes(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List all available API key scopes."""
    return [scope.value for scope in ApiKeyScope]
