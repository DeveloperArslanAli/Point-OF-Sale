"""SQLAlchemy models for report builder."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.session import Base
from app.infrastructure.db.utils import utcnow


class ReportDefinitionModel(Base):
    """SQLAlchemy model for report definitions."""

    __tablename__ = "report_definitions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Stored as JSON
    columns: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    group_by: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    schedule: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    default_format: Mapped[str] = mapped_column(String(20), nullable=False, default="json")
    
    # Ownership
    owner_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Timestamps and versioning
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=0)


class ReportExecutionModel(Base):
    """SQLAlchemy model for report executions."""

    __tablename__ = "report_executions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    report_definition_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Execution parameters (overrides from definition)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    
    # Results
    result_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    
    # Ownership
    requested_by: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
