"""Audit service for recording security and compliance events.

This module provides a centralized way to record audit events throughout
the application. It captures before/after state snapshots, request context,
and categorizes events for filtering and compliance reporting.

Usage:
    from app.application.auth.audit_service import AuditService
    
    audit = AuditService(audit_repo, request)
    await audit.log_user_action(
        actor_id=current_user.id,
        action="user.role_change",
        target_id=user.id,
        before_state={"role": "CASHIER"},
        after_state={"role": "MANAGER"},
    )
"""
from __future__ import annotations

import structlog
from starlette.requests import Request

from app.domain.auth.admin_action_log import (
    AdminActionLog,
    AuditCategory,
    AuditSeverity,
)
from app.infrastructure.db.repositories.admin_action_log_repository import (
    AdminActionLogRepository,
)

logger = structlog.get_logger()


class AuditService:
    """Service for recording audit events with request context."""

    def __init__(
        self,
        repo: AdminActionLogRepository,
        request: Request | None = None,
    ) -> None:
        self._repo = repo
        self._request = request

    def _get_ip_address(self) -> str | None:
        """Extract client IP from request."""
        if not self._request:
            return None
        # Check for forwarded header (behind proxy)
        forwarded = self._request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if self._request.client:
            return self._request.client.host
        return None

    def _get_user_agent(self) -> str | None:
        """Extract user agent from request."""
        if not self._request:
            return None
        return self._request.headers.get("user-agent")

    def _get_trace_id(self) -> str | None:
        """Extract trace ID from request state or headers."""
        if not self._request:
            return None
        # Try request state first (set by middleware)
        trace_id = getattr(self._request.state, "trace_id", None)
        if trace_id:
            return str(trace_id)
        # Fall back to header
        return self._request.headers.get("x-trace-id")

    async def log_user_action(
        self,
        *,
        actor_id: str,
        action: str,
        target_id: str | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        details: dict | None = None,
        severity: AuditSeverity = AuditSeverity.MEDIUM,
    ) -> None:
        """Log a user management action."""
        log = AdminActionLog.create(
            actor_user_id=actor_id,
            target_user_id=target_id,
            action=action,
            details=details,
            trace_id=self._get_trace_id(),
            category=AuditCategory.USER_MGMT,
            severity=severity,
            entity_type="User",
            entity_id=target_id,
            before_state=before_state,
            after_state=after_state,
            ip_address=self._get_ip_address(),
            user_agent=self._get_user_agent(),
        )
        await self._repo.add(log)
        logger.info(
            "audit_event_recorded",
            action=action,
            actor_id=actor_id,
            target_id=target_id,
            category="user_mgmt",
        )

    async def log_inventory_action(
        self,
        *,
        actor_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        before_state: dict | None = None,
        after_state: dict | None = None,
        details: dict | None = None,
    ) -> None:
        """Log an inventory-related action."""
        log = AdminActionLog.create(
            actor_user_id=actor_id,
            action=action,
            details=details,
            trace_id=self._get_trace_id(),
            category=AuditCategory.INVENTORY,
            severity=AuditSeverity.MEDIUM,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            ip_address=self._get_ip_address(),
            user_agent=self._get_user_agent(),
        )
        await self._repo.add(log)
        logger.info(
            "audit_event_recorded",
            action=action,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            category="inventory",
        )

    async def log_sales_action(
        self,
        *,
        actor_id: str,
        action: str,
        entity_id: str,
        customer_id: str | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        details: dict | None = None,
    ) -> None:
        """Log a sales-related action."""
        log = AdminActionLog.create(
            actor_user_id=actor_id,
            action=action,
            details={**(details or {}), "customer_id": customer_id},
            trace_id=self._get_trace_id(),
            category=AuditCategory.SALES,
            severity=AuditSeverity.MEDIUM,
            entity_type="Sale",
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            ip_address=self._get_ip_address(),
            user_agent=self._get_user_agent(),
        )
        await self._repo.add(log)
        logger.info(
            "audit_event_recorded",
            action=action,
            actor_id=actor_id,
            entity_id=entity_id,
            category="sales",
        )

    async def log_payment_action(
        self,
        *,
        actor_id: str,
        action: str,
        payment_id: str,
        sale_id: str | None = None,
        amount: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Log a payment-related action."""
        log = AdminActionLog.create(
            actor_user_id=actor_id,
            action=action,
            details={**(details or {}), "sale_id": sale_id, "amount": amount},
            trace_id=self._get_trace_id(),
            category=AuditCategory.PAYMENT,
            severity=AuditSeverity.HIGH,  # Payments are sensitive
            entity_type="Payment",
            entity_id=payment_id,
            ip_address=self._get_ip_address(),
            user_agent=self._get_user_agent(),
        )
        await self._repo.add(log)
        logger.info(
            "audit_event_recorded",
            action=action,
            actor_id=actor_id,
            payment_id=payment_id,
            category="payment",
        )

    async def log_security_event(
        self,
        *,
        actor_id: str,
        action: str,
        details: dict | None = None,
        success: bool = True,
    ) -> None:
        """Log a security-related event (login, logout, access denied, etc.)."""
        severity = AuditSeverity.MEDIUM if success else AuditSeverity.CRITICAL
        log = AdminActionLog.create(
            actor_user_id=actor_id,
            action=action,
            details={**(details or {}), "success": success},
            trace_id=self._get_trace_id(),
            category=AuditCategory.SECURITY,
            severity=severity,
            ip_address=self._get_ip_address(),
            user_agent=self._get_user_agent(),
        )
        await self._repo.add(log)
        logger.info(
            "security_event_recorded",
            action=action,
            actor_id=actor_id,
            success=success,
        )

    async def log_config_change(
        self,
        *,
        actor_id: str,
        action: str,
        config_key: str,
        before_value: str | None = None,
        after_value: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Log a configuration change."""
        log = AdminActionLog.create(
            actor_user_id=actor_id,
            action=action,
            details={**(details or {}), "config_key": config_key},
            trace_id=self._get_trace_id(),
            category=AuditCategory.CONFIG,
            severity=AuditSeverity.HIGH,
            entity_type="Config",
            entity_id=config_key,
            before_state={"value": before_value} if before_value else {},
            after_state={"value": after_value} if after_value else {},
            ip_address=self._get_ip_address(),
            user_agent=self._get_user_agent(),
        )
        await self._repo.add(log)
        logger.info(
            "config_change_recorded",
            action=action,
            actor_id=actor_id,
            config_key=config_key,
        )
