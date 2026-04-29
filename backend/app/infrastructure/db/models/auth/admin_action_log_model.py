from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.session import Base
from app.infrastructure.db.utils import utcnow


class AdminActionLogModel(Base):
    """Comprehensive audit log for security and compliance.
    
    Captures all sensitive operations with before/after state snapshots,
    request context (IP, user agent), and categorization for filtering.
    """
    __tablename__ = "admin_action_logs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    actor_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    
    # Enhanced audit fields for compliance
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="user_mgmt", index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium", index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    before_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    after_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # Supports IPv6
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        Index("ix_admin_action_logs_actor_target", "actor_user_id", "target_user_id"),
        Index("ix_admin_action_logs_entity", "entity_type", "entity_id"),
        Index("ix_admin_action_logs_security", "category", "severity", "created_at"),
    )
