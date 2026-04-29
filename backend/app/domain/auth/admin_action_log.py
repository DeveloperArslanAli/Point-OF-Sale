from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.domain.common.identifiers import new_ulid


class AuditSeverity(str, Enum):
    """Severity level for audit events."""
    LOW = "low"          # Info/read operations
    MEDIUM = "medium"    # Standard mutations
    HIGH = "high"        # Sensitive operations (password, role change)
    CRITICAL = "critical"  # Security events (login failure, access denied)


class AuditCategory(str, Enum):
    """Category of audit event for filtering."""
    AUTH = "auth"              # Login, logout, token operations
    USER_MGMT = "user_mgmt"    # User CRUD, role changes
    INVENTORY = "inventory"    # Stock adjustments, movements
    SALES = "sales"            # Transactions, refunds
    PAYMENT = "payment"        # Payment processing
    CONFIG = "config"          # System configuration changes
    SECURITY = "security"      # Security-related events


@dataclass(slots=True)
class AdminActionLog:
    """Comprehensive audit log entry for security and compliance.
    
    Captures:
    - Actor (who performed the action)
    - Target (what entity was affected)
    - Action details with before/after state
    - Request context (trace_id, IP, user agent)
    """
    id: str
    actor_user_id: str
    target_user_id: str | None
    action: str
    details: dict[str, Any]
    trace_id: str | None
    created_at: datetime
    # Enhanced audit fields
    category: str = "user_mgmt"
    severity: str = "medium"
    entity_type: str | None = None
    entity_id: str | None = None
    before_state: dict[str, Any] = field(default_factory=dict)
    after_state: dict[str, Any] = field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None

    @staticmethod
    def create(
        *,
        actor_user_id: str,
        target_user_id: str | None = None,
        action: str,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        category: AuditCategory = AuditCategory.USER_MGMT,
        severity: AuditSeverity = AuditSeverity.MEDIUM,
        entity_type: str | None = None,
        entity_id: str | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AdminActionLog:
        """Create a new audit log entry.
        
        Args:
            actor_user_id: User who performed the action
            target_user_id: User affected (if applicable)
            action: Action name (e.g., 'user.deactivate', 'inventory.adjust')
            details: Additional action details
            trace_id: Request trace ID for correlation
            category: Audit category for filtering
            severity: Severity level
            entity_type: Type of entity affected (e.g., 'Product', 'Sale')
            entity_id: ID of entity affected
            before_state: State before the action
            after_state: State after the action
            ip_address: Client IP address
            user_agent: Client user agent
        """
        return AdminActionLog(
            id=new_ulid(),
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            action=action,
            details=dict(details) if details else {},
            trace_id=trace_id,
            created_at=datetime.now(UTC),
            category=category.value if isinstance(category, AuditCategory) else category,
            severity=severity.value if isinstance(severity, AuditSeverity) else severity,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=dict(before_state) if before_state else {},
            after_state=dict(after_state) if after_state else {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def security_event(
        *,
        actor_user_id: str,
        action: str,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AdminActionLog:
        """Create a security-related audit event (login failure, access denied, etc.)."""
        return AdminActionLog.create(
            actor_user_id=actor_user_id,
            action=action,
            details=details,
            trace_id=trace_id,
            category=AuditCategory.SECURITY,
            severity=AuditSeverity.CRITICAL,
            ip_address=ip_address,
            user_agent=user_agent,
        )

