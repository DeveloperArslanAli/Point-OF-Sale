"""API Key domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from app.domain.common.identifiers import new_ulid


class ApiKeyScope(str, Enum):
    """API Key permission scopes."""
    
    READ_PRODUCTS = "read:products"
    WRITE_PRODUCTS = "write:products"
    READ_INVENTORY = "read:inventory"
    WRITE_INVENTORY = "write:inventory"
    READ_SALES = "read:sales"
    WRITE_SALES = "write:sales"
    READ_CUSTOMERS = "read:customers"
    WRITE_CUSTOMERS = "write:customers"
    READ_REPORTS = "read:reports"
    WEBHOOKS = "webhooks"
    FULL_ACCESS = "full_access"


class ApiKeyStatus(str, Enum):
    """API Key status."""
    
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass
class ApiKey:
    """API Key entity for external integrations."""
    
    id: str = field(default_factory=new_ulid)
    tenant_id: str = ""
    name: str = ""
    key_prefix: str = ""  # First 8 chars of the key for identification
    key_hash: str = ""  # Argon2 hash of the full key
    scopes: list[str] = field(default_factory=list)
    rate_limit_per_minute: int = 60
    status: ApiKeyStatus = ApiKeyStatus.ACTIVE
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    version: int = 0
    
    def is_valid(self) -> bool:
        """Check if API key is valid for use."""
        if self.status != ApiKeyStatus.ACTIVE:
            return False
        if self.expires_at and datetime.now(UTC) > self.expires_at:
            return False
        return True
    
    def has_scope(self, scope: str) -> bool:
        """Check if key has the required scope."""
        if ApiKeyScope.FULL_ACCESS.value in self.scopes:
            return True
        return scope in self.scopes
    
    def revoke(self, revoked_by: str) -> None:
        """Revoke the API key."""
        self.status = ApiKeyStatus.REVOKED
        self.revoked_at = datetime.now(UTC)
        self.revoked_by = revoked_by
        self.version += 1
    
    def record_usage(self) -> None:
        """Record API key usage."""
        self.last_used_at = datetime.now(UTC)
