"""Pydantic schemas for reports API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportColumnSchema(BaseModel):
    """Schema for report column configuration."""
    field: str
    label: str
    visible: bool = True
    sort_order: int | None = None
    sort_direction: str | None = None  # asc, desc
    aggregate: str | None = None  # sum, avg, count, min, max
    format: str | None = None


class ReportFilterSchema(BaseModel):
    """Schema for report filter."""
    field: str
    operator: str  # eq, ne, gt, gte, lt, lte, contains, in, between, etc.
    value: Any
    value2: Any | None = None  # For BETWEEN operator


class ReportScheduleSchema(BaseModel):
    """Schema for report schedule."""
    frequency: str  # once, daily, weekly, monthly
    day_of_week: int | None = None  # 0=Monday for weekly
    day_of_month: int | None = None  # 1-31 for monthly
    time_of_day: str = "00:00"  # HH:MM
    timezone: str = "UTC"
    recipients: list[str] = Field(default_factory=list)
    enabled: bool = True


class CreateReportDefinitionRequest(BaseModel):
    """Request to create a report definition."""
    name: str = Field(..., min_length=3, max_length=255)
    report_type: str  # sales, inventory, customers, etc.
    description: str = ""
    columns: list[ReportColumnSchema] | None = None
    filters: list[ReportFilterSchema] | None = None
    group_by: list[str] | None = None
    default_format: str = "json"  # json, csv, excel, pdf
    schedule: ReportScheduleSchema | None = None
    is_public: bool = False


class UpdateReportDefinitionRequest(BaseModel):
    """Request to update a report definition."""
    name: str | None = Field(None, min_length=3, max_length=255)
    description: str | None = None
    columns: list[ReportColumnSchema] | None = None
    filters: list[ReportFilterSchema] | None = None
    group_by: list[str] | None = None
    default_format: str | None = None
    schedule: ReportScheduleSchema | None = None
    is_public: bool | None = None


class GenerateReportRequest(BaseModel):
    """Request to generate a report."""
    format: str | None = None  # Override default format
    parameters: dict[str, Any] | None = None  # Runtime filter overrides


class ReportDefinitionResponse(BaseModel):
    """Response containing a report definition."""
    id: str
    name: str
    description: str
    report_type: str
    columns: list[ReportColumnSchema]
    filters: list[ReportFilterSchema]
    group_by: list[str]
    default_format: str
    schedule: ReportScheduleSchema | None
    owner_id: str | None
    tenant_id: str | None
    is_public: bool
    created_at: datetime
    updated_at: datetime
    version: int


class ReportExecutionResponse(BaseModel):
    """Response containing a report execution."""
    id: str
    report_definition_id: str
    status: str
    format: str
    parameters: dict[str, Any]
    result_path: str | None
    row_count: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    requested_by: str | None


class GenerateReportResponse(BaseModel):
    """Response from generating a report."""
    execution_id: str
    status: str
    format: str
    row_count: int
    download_url: str | None = None
