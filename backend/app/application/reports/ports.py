"""Report repository port (interface)."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domain.reports.entities import (
        ReportDefinition,
        ReportExecution,
        ReportStatus,
        ReportType,
    )


class IReportDefinitionRepository(Protocol):
    """Port for report definition persistence."""

    @abstractmethod
    async def add(self, definition: ReportDefinition) -> None:
        """Add a new report definition."""
        ...

    @abstractmethod
    async def get_by_id(self, definition_id: str) -> ReportDefinition | None:
        """Get a report definition by ID."""
        ...

    @abstractmethod
    async def get_all_for_tenant(
        self,
        tenant_id: str,
        *,
        report_type: ReportType | None = None,
        owner_id: str | None = None,
        include_public: bool = True,
        offset: int = 0,
        limit: int = 50,
    ) -> list[ReportDefinition]:
        """Get all report definitions for a tenant."""
        ...

    @abstractmethod
    async def get_scheduled(self) -> list[ReportDefinition]:
        """Get all report definitions with active schedules."""
        ...

    @abstractmethod
    async def update(
        self, definition: ReportDefinition, expected_version: int
    ) -> None:
        """Update a report definition with optimistic locking."""
        ...

    @abstractmethod
    async def delete(self, definition_id: str) -> bool:
        """Delete a report definition. Returns True if deleted."""
        ...

    @abstractmethod
    async def count_for_tenant(
        self,
        tenant_id: str,
        *,
        report_type: ReportType | None = None,
    ) -> int:
        """Count report definitions for a tenant."""
        ...


class IReportExecutionRepository(Protocol):
    """Port for report execution persistence."""

    @abstractmethod
    async def add(self, execution: ReportExecution) -> None:
        """Add a new report execution."""
        ...

    @abstractmethod
    async def get_by_id(self, execution_id: str) -> ReportExecution | None:
        """Get a report execution by ID."""
        ...

    @abstractmethod
    async def get_for_definition(
        self,
        definition_id: str,
        *,
        status: ReportStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[ReportExecution]:
        """Get executions for a report definition."""
        ...

    @abstractmethod
    async def get_pending(self) -> list[ReportExecution]:
        """Get all pending executions."""
        ...

    @abstractmethod
    async def update(self, execution: ReportExecution) -> None:
        """Update a report execution."""
        ...

    @abstractmethod
    async def delete_old(self, days: int = 30) -> int:
        """Delete executions older than given days. Returns count deleted."""
        ...


class IReportDataProvider(Protocol):
    """Interface for fetching report data."""

    @abstractmethod
    async def fetch_data(
        self,
        definition: ReportDefinition,
        parameters: dict[str, object],
    ) -> list[dict[str, object]]:
        """Fetch data for a report definition."""
        ...
