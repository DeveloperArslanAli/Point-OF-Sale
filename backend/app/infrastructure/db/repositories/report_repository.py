"""SQLAlchemy repository implementations for reports."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Sequence

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.reports.ports import (
    IReportDefinitionRepository,
    IReportExecutionRepository,
)
from app.domain.common.errors import ConflictError
from app.domain.reports.entities import (
    FilterOperator,
    ReportColumn,
    ReportDefinition,
    ReportExecution,
    ReportFilter,
    ReportFormat,
    ReportSchedule,
    ReportStatus,
    ReportType,
    ScheduleFrequency,
    SortDirection,
)
from app.infrastructure.db.models.report_model import (
    ReportDefinitionModel,
    ReportExecutionModel,
)


class SqlAlchemyReportDefinitionRepository(IReportDefinitionRepository):
    """SQLAlchemy implementation of report definition repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, definition: ReportDefinition) -> None:
        model = self._to_model(definition)
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, definition_id: str) -> ReportDefinition | None:
        stmt = select(ReportDefinitionModel).where(
            ReportDefinitionModel.id == definition_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

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
        # Build base query for tenant
        if include_public:
            tenant_clause = or_(
                ReportDefinitionModel.tenant_id == tenant_id,
                ReportDefinitionModel.is_public == True,  # noqa: E712
            )
        else:
            tenant_clause = ReportDefinitionModel.tenant_id == tenant_id

        stmt = select(ReportDefinitionModel).where(tenant_clause)

        if report_type:
            stmt = stmt.where(ReportDefinitionModel.report_type == report_type.value)

        if owner_id:
            stmt = stmt.where(ReportDefinitionModel.owner_id == owner_id)

        stmt = (
            stmt.order_by(ReportDefinitionModel.name.asc())
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def get_scheduled(self) -> list[ReportDefinition]:
        """Get all definitions with active schedules that need to run."""
        stmt = select(ReportDefinitionModel).where(
            ReportDefinitionModel.schedule.isnot(None)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        
        # Filter to enabled schedules
        definitions = []
        for model in models:
            entity = self._to_entity(model)
            if entity.schedule and entity.schedule.enabled:
                definitions.append(entity)
        return definitions

    async def update(
        self, definition: ReportDefinition, expected_version: int
    ) -> None:
        stmt = select(ReportDefinitionModel).where(
            ReportDefinitionModel.id == definition.id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return

        if model.version != expected_version:
            raise ConflictError(
                f"Report definition {definition.id} was modified by another request",
                code="report.definition.conflict",
            )

        # Update fields
        model.name = definition.name
        model.description = definition.description
        model.report_type = definition.report_type.value
        model.columns = [self._column_to_dict(c) for c in definition.columns]
        model.filters = [self._filter_to_dict(f) for f in definition.filters]
        model.group_by = definition.group_by
        model.default_format = definition.default_format.value
        model.schedule = self._schedule_to_dict(definition.schedule) if definition.schedule else None
        model.is_public = definition.is_public
        model.updated_at = definition.updated_at
        model.version = definition.version

        await self._session.flush()

    async def delete(self, definition_id: str) -> bool:
        stmt = delete(ReportDefinitionModel).where(
            ReportDefinitionModel.id == definition_id
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def count_for_tenant(
        self,
        tenant_id: str,
        *,
        report_type: ReportType | None = None,
    ) -> int:
        stmt = select(func.count(ReportDefinitionModel.id)).where(
            ReportDefinitionModel.tenant_id == tenant_id
        )
        if report_type:
            stmt = stmt.where(ReportDefinitionModel.report_type == report_type.value)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    def _to_model(self, entity: ReportDefinition) -> ReportDefinitionModel:
        return ReportDefinitionModel(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            report_type=entity.report_type.value,
            columns=[self._column_to_dict(c) for c in entity.columns],
            filters=[self._filter_to_dict(f) for f in entity.filters],
            group_by=entity.group_by,
            default_format=entity.default_format.value,
            schedule=self._schedule_to_dict(entity.schedule) if entity.schedule else None,
            owner_id=entity.owner_id,
            tenant_id=entity.tenant_id,
            is_public=entity.is_public,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            version=entity.version,
        )

    def _to_entity(self, model: ReportDefinitionModel) -> ReportDefinition:
        return ReportDefinition(
            id=model.id,
            name=model.name,
            description=model.description,
            report_type=ReportType(model.report_type),
            columns=[self._dict_to_column(c) for c in (model.columns or [])],
            filters=[self._dict_to_filter(f) for f in (model.filters or [])],
            group_by=model.group_by or [],
            default_format=ReportFormat(model.default_format),
            schedule=self._dict_to_schedule(model.schedule) if model.schedule else None,
            owner_id=model.owner_id,
            tenant_id=model.tenant_id,
            is_public=model.is_public,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    @staticmethod
    def _column_to_dict(column: ReportColumn) -> dict:
        return {
            "field": column.field,
            "label": column.label,
            "visible": column.visible,
            "sort_order": column.sort_order,
            "sort_direction": column.sort_direction.value if column.sort_direction else None,
            "aggregate": column.aggregate,
            "format": column.format,
        }

    @staticmethod
    def _dict_to_column(data: dict) -> ReportColumn:
        return ReportColumn(
            field=data["field"],
            label=data["label"],
            visible=data.get("visible", True),
            sort_order=data.get("sort_order"),
            sort_direction=SortDirection(data["sort_direction"]) if data.get("sort_direction") else None,
            aggregate=data.get("aggregate"),
            format=data.get("format"),
        )

    @staticmethod
    def _filter_to_dict(filter_: ReportFilter) -> dict:
        return {
            "field": filter_.field,
            "operator": filter_.operator.value,
            "value": filter_.value,
            "value2": filter_.value2,
        }

    @staticmethod
    def _dict_to_filter(data: dict) -> ReportFilter:
        return ReportFilter(
            field=data["field"],
            operator=FilterOperator(data["operator"]),
            value=data["value"],
            value2=data.get("value2"),
        )

    @staticmethod
    def _schedule_to_dict(schedule: ReportSchedule) -> dict:
        return {
            "frequency": schedule.frequency.value,
            "day_of_week": schedule.day_of_week,
            "day_of_month": schedule.day_of_month,
            "time_of_day": schedule.time_of_day,
            "timezone": schedule.timezone,
            "recipients": schedule.recipients,
            "enabled": schedule.enabled,
            "next_run_at": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        }

    @staticmethod
    def _dict_to_schedule(data: dict) -> ReportSchedule:
        next_run = None
        if data.get("next_run_at"):
            next_run = datetime.fromisoformat(data["next_run_at"])
        return ReportSchedule(
            frequency=ScheduleFrequency(data["frequency"]),
            day_of_week=data.get("day_of_week"),
            day_of_month=data.get("day_of_month"),
            time_of_day=data.get("time_of_day", "00:00"),
            timezone=data.get("timezone", "UTC"),
            recipients=data.get("recipients", []),
            enabled=data.get("enabled", True),
            next_run_at=next_run,
        )


class SqlAlchemyReportExecutionRepository(IReportExecutionRepository):
    """SQLAlchemy implementation of report execution repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, execution: ReportExecution) -> None:
        model = self._to_model(execution)
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, execution_id: str) -> ReportExecution | None:
        stmt = select(ReportExecutionModel).where(
            ReportExecutionModel.id == execution_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_for_definition(
        self,
        definition_id: str,
        *,
        status: ReportStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[ReportExecution]:
        stmt = select(ReportExecutionModel).where(
            ReportExecutionModel.report_definition_id == definition_id
        )

        if status:
            stmt = stmt.where(ReportExecutionModel.status == status.value)

        stmt = (
            stmt.order_by(ReportExecutionModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def get_pending(self) -> list[ReportExecution]:
        stmt = select(ReportExecutionModel).where(
            ReportExecutionModel.status == ReportStatus.PENDING.value
        ).order_by(ReportExecutionModel.created_at.asc())

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def update(self, execution: ReportExecution) -> None:
        stmt = select(ReportExecutionModel).where(
            ReportExecutionModel.id == execution.id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return

        model.status = execution.status.value
        model.result_path = execution.result_path
        model.row_count = execution.row_count
        model.error_message = execution.error_message
        model.started_at = execution.started_at
        model.completed_at = execution.completed_at

        await self._session.flush()

    async def delete_old(self, days: int = 30) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = delete(ReportExecutionModel).where(
            ReportExecutionModel.created_at < cutoff
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    def _to_model(self, entity: ReportExecution) -> ReportExecutionModel:
        return ReportExecutionModel(
            id=entity.id,
            report_definition_id=entity.report_definition_id,
            status=entity.status.value,
            format=entity.format.value,
            parameters=entity.parameters,
            result_path=entity.result_path,
            row_count=entity.row_count,
            error_message=entity.error_message,
            started_at=entity.started_at,
            completed_at=entity.completed_at,
            created_at=entity.created_at,
            requested_by=entity.requested_by,
            tenant_id=entity.tenant_id,
        )

    def _to_entity(self, model: ReportExecutionModel) -> ReportExecution:
        return ReportExecution(
            id=model.id,
            report_definition_id=model.report_definition_id,
            status=ReportStatus(model.status),
            format=ReportFormat(model.format),
            parameters=model.parameters or {},
            result_path=model.result_path,
            row_count=model.row_count,
            error_message=model.error_message,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            requested_by=model.requested_by,
            tenant_id=model.tenant_id,
        )
