"""Report domain entities for custom report builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.domain.common.errors import ValidationError
from app.domain.common.identifiers import new_ulid


class ReportType(str, Enum):
    """Types of reports available."""
    SALES = "sales"
    INVENTORY = "inventory"
    CUSTOMERS = "customers"
    EMPLOYEES = "employees"
    PURCHASES = "purchases"
    RETURNS = "returns"
    GIFT_CARDS = "gift_cards"
    PROMOTIONS = "promotions"
    CUSTOM = "custom"


class ReportFormat(str, Enum):
    """Output formats for reports."""
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"


class ScheduleFrequency(str, Enum):
    """Frequency for scheduled reports."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ReportStatus(str, Enum):
    """Status of report generation."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FilterOperator(str, Enum):
    """Filter operators for report queries."""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_OR_EQUAL = "lte"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class SortDirection(str, Enum):
    """Sort direction for report columns."""
    ASC = "asc"
    DESC = "desc"


@dataclass(slots=True)
class ReportFilter:
    """A filter condition for report data."""
    field: str
    operator: FilterOperator
    value: Any
    value2: Any | None = None  # For BETWEEN operator

    def validate(self) -> None:
        """Validate filter configuration."""
        if not self.field:
            raise ValidationError("Filter field is required", code="report.filter.invalid_field")
        if self.operator == FilterOperator.BETWEEN and self.value2 is None:
            raise ValidationError(
                "BETWEEN operator requires two values",
                code="report.filter.invalid_between",
            )


@dataclass(slots=True)
class ReportColumn:
    """A column configuration for report output."""
    field: str
    label: str
    visible: bool = True
    sort_order: int | None = None
    sort_direction: SortDirection | None = None
    aggregate: str | None = None  # sum, avg, count, min, max
    format: str | None = None  # date format, number format, etc.


@dataclass(slots=True)
class ReportSchedule:
    """Schedule configuration for automated report generation."""
    frequency: ScheduleFrequency
    day_of_week: int | None = None  # 0=Monday for WEEKLY
    day_of_month: int | None = None  # 1-31 for MONTHLY
    time_of_day: str = "00:00"  # HH:MM format
    timezone: str = "UTC"
    recipients: list[str] = field(default_factory=list)  # Email addresses
    enabled: bool = True
    next_run_at: datetime | None = None

    def validate(self) -> None:
        """Validate schedule configuration."""
        if self.frequency == ScheduleFrequency.WEEKLY and self.day_of_week is None:
            raise ValidationError(
                "Weekly schedule requires day_of_week",
                code="report.schedule.invalid_weekly",
            )
        if self.frequency == ScheduleFrequency.MONTHLY and self.day_of_month is None:
            raise ValidationError(
                "Monthly schedule requires day_of_month",
                code="report.schedule.invalid_monthly",
            )


@dataclass(slots=True)
class ReportDefinition:
    """
    A saved report definition that can be regenerated.
    
    Contains all configuration needed to generate a report:
    - Report type and metadata
    - Column configuration
    - Filters
    - Grouping and aggregation
    - Schedule for automation
    """
    id: str
    name: str
    description: str
    report_type: ReportType
    columns: list[ReportColumn] = field(default_factory=list)
    filters: list[ReportFilter] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    default_format: ReportFormat = ReportFormat.JSON
    schedule: ReportSchedule | None = None
    owner_id: str | None = None  # User who created the report
    tenant_id: str | None = None
    is_public: bool = False  # Shared with all users in tenant
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0

    @staticmethod
    def create(
        *,
        name: str,
        report_type: ReportType | str,
        description: str = "",
        columns: list[ReportColumn] | None = None,
        filters: list[ReportFilter] | None = None,
        group_by: list[str] | None = None,
        default_format: ReportFormat | str = ReportFormat.JSON,
        schedule: ReportSchedule | None = None,
        owner_id: str | None = None,
        tenant_id: str | None = None,
        is_public: bool = False,
    ) -> ReportDefinition:
        """Create a new report definition."""
        if not name or len(name.strip()) < 3:
            raise ValidationError(
                "Report name must be at least 3 characters",
                code="report.invalid_name",
            )
        
        if isinstance(report_type, str):
            report_type = ReportType(report_type)
        
        if isinstance(default_format, str):
            default_format = ReportFormat(default_format)

        # Validate filters
        for f in filters or []:
            f.validate()

        # Validate schedule
        if schedule:
            schedule.validate()

        return ReportDefinition(
            id=new_ulid(),
            name=name.strip(),
            description=description,
            report_type=report_type,
            columns=columns or [],
            filters=filters or [],
            group_by=group_by or [],
            default_format=default_format,
            schedule=schedule,
            owner_id=owner_id,
            tenant_id=tenant_id,
            is_public=is_public,
        )

    def update(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        columns: list[ReportColumn] | None = None,
        filters: list[ReportFilter] | None = None,
        group_by: list[str] | None = None,
        default_format: ReportFormat | None = None,
        schedule: ReportSchedule | None = None,
        is_public: bool | None = None,
    ) -> None:
        """Update report definition."""
        if name is not None:
            if len(name.strip()) < 3:
                raise ValidationError(
                    "Report name must be at least 3 characters",
                    code="report.invalid_name",
                )
            self.name = name.strip()
        
        if description is not None:
            self.description = description
        
        if columns is not None:
            self.columns = columns
        
        if filters is not None:
            for f in filters:
                f.validate()
            self.filters = filters
        
        if group_by is not None:
            self.group_by = group_by
        
        if default_format is not None:
            self.default_format = default_format
        
        if schedule is not None:
            schedule.validate()
            self.schedule = schedule
        
        if is_public is not None:
            self.is_public = is_public
        
        self.updated_at = datetime.now(UTC)
        self.version += 1


@dataclass(slots=True)
class ReportExecution:
    """
    A single execution of a report.
    
    Tracks the status and results of report generation.
    """
    id: str
    report_definition_id: str
    status: ReportStatus
    format: ReportFormat
    parameters: dict[str, Any] = field(default_factory=dict)
    result_path: str | None = None  # Path to generated file
    row_count: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    requested_by: str | None = None  # User who requested
    tenant_id: str | None = None

    @staticmethod
    def create(
        *,
        report_definition_id: str,
        format: ReportFormat | str = ReportFormat.JSON,
        parameters: dict[str, Any] | None = None,
        requested_by: str | None = None,
        tenant_id: str | None = None,
    ) -> ReportExecution:
        """Create a new report execution record."""
        if isinstance(format, str):
            format = ReportFormat(format)
        
        return ReportExecution(
            id=new_ulid(),
            report_definition_id=report_definition_id,
            status=ReportStatus.PENDING,
            format=format,
            parameters=parameters or {},
            requested_by=requested_by,
            tenant_id=tenant_id,
        )

    def start(self) -> None:
        """Mark execution as started."""
        if self.status != ReportStatus.PENDING:
            raise ValidationError(
                f"Cannot start execution in {self.status} status",
                code="report.execution.invalid_start",
            )
        self.status = ReportStatus.GENERATING
        self.started_at = datetime.now(UTC)

    def complete(self, result_path: str, row_count: int) -> None:
        """Mark execution as completed successfully."""
        if self.status != ReportStatus.GENERATING:
            raise ValidationError(
                f"Cannot complete execution in {self.status} status",
                code="report.execution.invalid_complete",
            )
        self.status = ReportStatus.COMPLETED
        self.result_path = result_path
        self.row_count = row_count
        self.completed_at = datetime.now(UTC)

    def fail(self, error_message: str) -> None:
        """Mark execution as failed."""
        self.status = ReportStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now(UTC)

    def cancel(self) -> None:
        """Cancel the execution."""
        if self.status not in (ReportStatus.PENDING, ReportStatus.GENERATING):
            raise ValidationError(
                f"Cannot cancel execution in {self.status} status",
                code="report.execution.invalid_cancel",
            )
        self.status = ReportStatus.CANCELLED
        self.completed_at = datetime.now(UTC)
