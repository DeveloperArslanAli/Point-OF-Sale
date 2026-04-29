"""Use case for creating a report definition."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.reports.ports import IReportDefinitionRepository
from app.domain.reports.entities import (
    ReportColumn,
    ReportDefinition,
    ReportFilter,
    ReportFormat,
    ReportSchedule,
    ReportType,
)


@dataclass(frozen=True, slots=True)
class CreateReportDefinitionCommand:
    """Command to create a report definition."""
    name: str
    report_type: str
    description: str = ""
    columns: list[dict] | None = None
    filters: list[dict] | None = None
    group_by: list[str] | None = None
    default_format: str = "json"
    schedule: dict | None = None
    owner_id: str | None = None
    tenant_id: str | None = None
    is_public: bool = False


@dataclass(frozen=True, slots=True)
class CreateReportDefinitionResult:
    """Result of creating a report definition."""
    definition: ReportDefinition


class CreateReportDefinitionUseCase:
    """Use case for creating a new report definition."""

    def __init__(
        self,
        report_definition_repo: IReportDefinitionRepository,
    ) -> None:
        self._repo = report_definition_repo

    async def execute(
        self, command: CreateReportDefinitionCommand
    ) -> CreateReportDefinitionResult:
        # Convert columns from dicts
        columns = None
        if command.columns:
            columns = [
                ReportColumn(
                    field=c["field"],
                    label=c.get("label", c["field"]),
                    visible=c.get("visible", True),
                    sort_order=c.get("sort_order"),
                    sort_direction=c.get("sort_direction"),
                    aggregate=c.get("aggregate"),
                    format=c.get("format"),
                )
                for c in command.columns
            ]

        # Convert filters from dicts
        filters = None
        if command.filters:
            from app.domain.reports.entities import FilterOperator
            filters = [
                ReportFilter(
                    field=f["field"],
                    operator=FilterOperator(f["operator"]),
                    value=f["value"],
                    value2=f.get("value2"),
                )
                for f in command.filters
            ]

        # Convert schedule from dict
        schedule = None
        if command.schedule:
            from app.domain.reports.entities import ScheduleFrequency
            schedule = ReportSchedule(
                frequency=ScheduleFrequency(command.schedule["frequency"]),
                day_of_week=command.schedule.get("day_of_week"),
                day_of_month=command.schedule.get("day_of_month"),
                time_of_day=command.schedule.get("time_of_day", "00:00"),
                timezone=command.schedule.get("timezone", "UTC"),
                recipients=command.schedule.get("recipients", []),
                enabled=command.schedule.get("enabled", True),
            )

        definition = ReportDefinition.create(
            name=command.name,
            report_type=command.report_type,
            description=command.description,
            columns=columns,
            filters=filters,
            group_by=command.group_by,
            default_format=command.default_format,
            schedule=schedule,
            owner_id=command.owner_id,
            tenant_id=command.tenant_id,
            is_public=command.is_public,
        )

        await self._repo.add(definition)

        return CreateReportDefinitionResult(definition=definition)
