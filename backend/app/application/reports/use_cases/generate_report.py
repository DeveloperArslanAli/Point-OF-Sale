"""Use case for generating a report."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.application.reports.ports import (
    IReportDefinitionRepository,
    IReportExecutionRepository,
)
from app.domain.common.errors import NotFoundError, ValidationError
from app.domain.reports.entities import (
    ReportDefinition,
    ReportExecution,
    ReportFormat,
    ReportStatus,
)
from app.infrastructure.reports.exporters import (
    CSVReportExporter,
    ExcelReportExporter,
    PDFReportExporter,
)


@dataclass(frozen=True, slots=True)
class GenerateReportCommand:
    """Command to generate a report."""
    definition_id: str
    format: str | None = None  # Override default format
    parameters: dict | None = None  # Runtime filter overrides
    requested_by: str | None = None
    tenant_id: str | None = None


@dataclass(frozen=True, slots=True)
class GenerateReportResult:
    """Result of report generation."""
    execution_id: str
    status: ReportStatus
    format: ReportFormat
    content: bytes | None = None  # For immediate results
    row_count: int = 0


class GenerateReportUseCase:
    """
    Use case for generating reports.
    
    This use case handles the execution of report definitions,
    applying filters, fetching data, and formatting output.
    """

    def __init__(
        self,
        definition_repo: IReportDefinitionRepository,
        execution_repo: IReportExecutionRepository,
        report_data_provider: IReportDataProvider,
    ) -> None:
        self._definition_repo = definition_repo
        self._execution_repo = execution_repo
        self._data_provider = report_data_provider

    async def execute(self, command: GenerateReportCommand) -> GenerateReportResult:
        # Get the report definition
        definition = await self._definition_repo.get_by_id(command.definition_id)
        if not definition:
            raise NotFoundError(
                f"Report definition {command.definition_id} not found",
                code="report.definition.not_found",
            )

        # Determine output format
        output_format = definition.default_format
        if command.format:
            output_format = ReportFormat(command.format)

        # Create execution record
        execution = ReportExecution.create(
            report_definition_id=definition.id,
            format=output_format,
            parameters=command.parameters or {},
            requested_by=command.requested_by,
            tenant_id=command.tenant_id or definition.tenant_id,
        )
        await self._execution_repo.add(execution)

        try:
            # Start execution
            execution.start()
            await self._execution_repo.update(execution)

            # Fetch data based on report type and filters
            data = await self._data_provider.fetch_data(
                definition=definition,
                parameters=command.parameters or {},
            )

            # Format output
            content = self._format_output(data, output_format, definition)

            # Save result (in production, save to file storage)
            result_path = f"reports/{execution.id}.{output_format.value}"
            
            # Complete execution
            execution.complete(result_path=result_path, row_count=len(data))
            await self._execution_repo.update(execution)

            return GenerateReportResult(
                execution_id=execution.id,
                status=ReportStatus.COMPLETED,
                format=output_format,
                content=content,
                row_count=len(data),
            )

        except Exception as e:
            execution.fail(str(e))
            await self._execution_repo.update(execution)
            raise

    def _format_output(
        self,
        data: list[dict[str, Any]],
        format_: ReportFormat,
        definition: ReportDefinition,
    ) -> bytes:
        """Format report data for output."""
        if format_ == ReportFormat.JSON:
            return self._format_json(data)
        elif format_ == ReportFormat.CSV:
            return self._format_csv(data, definition)
        elif format_ == ReportFormat.EXCEL:
            return self._format_excel(data, definition)
        elif format_ == ReportFormat.PDF:
            return self._format_pdf(data, definition)
        else:
            raise ValidationError(
                f"Unsupported format: {format_}",
                code="report.format.unsupported",
            )

    def _format_json(self, data: list[dict[str, Any]]) -> bytes:
        """Format as JSON."""
        return json.dumps(data, indent=2, default=str).encode("utf-8")

    def _format_csv(
        self, data: list[dict[str, Any]], definition: ReportDefinition
    ) -> bytes:
        """Format as CSV using CSVReportExporter."""
        exporter = CSVReportExporter()
        return exporter.export(data, definition)

    def _format_excel(
        self, data: list[dict[str, Any]], definition: ReportDefinition
    ) -> bytes:
        """Format as Excel using ExcelReportExporter with openpyxl."""
        exporter = ExcelReportExporter()
        return exporter.export(data, definition)

    def _format_pdf(
        self, data: list[dict[str, Any]], definition: ReportDefinition
    ) -> bytes:
        """Format as PDF using PDFReportExporter with ReportLab."""
        exporter = PDFReportExporter()
        return exporter.export(data, definition)
