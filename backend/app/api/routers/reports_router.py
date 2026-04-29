"""API router for report generation endpoints."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from celery.result import AsyncResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import MANAGEMENT_ROLES, require_roles
from app.api.schemas.report_schemas import (
    CreateReportDefinitionRequest,
    GenerateReportRequest,
    GenerateReportResponse,
    ReportColumnSchema,
    ReportDefinitionResponse,
    ReportExecutionResponse,
    ReportFilterSchema,
    ReportScheduleSchema,
    UpdateReportDefinitionRequest,
)
from app.application.reports.use_cases.create_report_definition import (
    CreateReportDefinitionCommand,
    CreateReportDefinitionUseCase,
)
from app.application.reports.use_cases.generate_report import (
    GenerateReportCommand,
    GenerateReportUseCase,
)
from app.domain.auth.entities import User
from app.domain.reports.entities import (
    FilterOperator,
    ReportColumn,
    ReportFilter,
    ReportFormat,
    ReportSchedule,
    ReportType,
    ScheduleFrequency,
)
from app.infrastructure.db.repositories.report_repository import (
    SqlAlchemyReportDefinitionRepository,
    SqlAlchemyReportExecutionRepository,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.reports.data_provider import SqlAlchemyReportDataProvider
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.report_tasks import (
    generate_sales_report,
    generate_inventory_report,
)
from app.infrastructure.tasks.email_tasks import send_report_email

router = APIRouter(prefix="/reports", tags=["reports"])


# ===============================
# Custom Report Builder Endpoints
# ===============================

def _definition_to_response(definition) -> ReportDefinitionResponse:
    """Convert domain entity to response schema."""
    return ReportDefinitionResponse(
        id=definition.id,
        name=definition.name,
        description=definition.description,
        report_type=definition.report_type.value,
        columns=[
            ReportColumnSchema(
                field=c.field,
                label=c.label,
                visible=c.visible,
                sort_order=c.sort_order,
                sort_direction=c.sort_direction.value if c.sort_direction else None,
                aggregate=c.aggregate,
                format=c.format,
            )
            for c in definition.columns
        ],
        filters=[
            ReportFilterSchema(
                field=f.field,
                operator=f.operator.value,
                value=f.value,
                value2=f.value2,
            )
            for f in definition.filters
        ],
        group_by=definition.group_by,
        default_format=definition.default_format.value,
        schedule=ReportScheduleSchema(
            frequency=definition.schedule.frequency.value,
            day_of_week=definition.schedule.day_of_week,
            day_of_month=definition.schedule.day_of_month,
            time_of_day=definition.schedule.time_of_day,
            timezone=definition.schedule.timezone,
            recipients=definition.schedule.recipients,
            enabled=definition.schedule.enabled,
        ) if definition.schedule else None,
        owner_id=definition.owner_id,
        tenant_id=definition.tenant_id,
        is_public=definition.is_public,
        created_at=definition.created_at,
        updated_at=definition.updated_at,
        version=definition.version,
    )


@router.post("/definitions", response_model=ReportDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_report_definition(
    payload: CreateReportDefinitionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> ReportDefinitionResponse:
    """Create a new custom report definition."""
    repo = SqlAlchemyReportDefinitionRepository(session)
    use_case = CreateReportDefinitionUseCase(repo)

    command = CreateReportDefinitionCommand(
        name=payload.name,
        report_type=payload.report_type,
        description=payload.description,
        columns=[c.model_dump() for c in payload.columns] if payload.columns else None,
        filters=[f.model_dump() for f in payload.filters] if payload.filters else None,
        group_by=payload.group_by,
        default_format=payload.default_format,
        schedule=payload.schedule.model_dump() if payload.schedule else None,
        owner_id=current_user.id,
        tenant_id=current_user.tenant_id,
        is_public=payload.is_public,
    )

    result = await use_case.execute(command)
    return _definition_to_response(result.definition)


@router.get("/definitions", response_model=list[ReportDefinitionResponse])
async def list_report_definitions(
    report_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> list[ReportDefinitionResponse]:
    """List custom report definitions for the tenant."""
    repo = SqlAlchemyReportDefinitionRepository(session)
    
    type_filter = ReportType(report_type) if report_type else None
    
    definitions = await repo.get_all_for_tenant(
        tenant_id=current_user.tenant_id or "",
        report_type=type_filter,
        owner_id=None,
        include_public=True,
        offset=offset,
        limit=limit,
    )
    
    return [_definition_to_response(d) for d in definitions]


@router.get("/definitions/{definition_id}", response_model=ReportDefinitionResponse)
async def get_report_definition(
    definition_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> ReportDefinitionResponse:
    """Get a custom report definition by ID."""
    repo = SqlAlchemyReportDefinitionRepository(session)
    definition = await repo.get_by_id(definition_id)
    
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report definition {definition_id} not found",
        )
    
    return _definition_to_response(definition)


@router.put("/definitions/{definition_id}", response_model=ReportDefinitionResponse)
async def update_report_definition(
    definition_id: str,
    payload: UpdateReportDefinitionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> ReportDefinitionResponse:
    """Update a custom report definition."""
    repo = SqlAlchemyReportDefinitionRepository(session)
    definition = await repo.get_by_id(definition_id)
    
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report definition {definition_id} not found",
        )
    
    # Build update kwargs
    update_kwargs: dict[str, Any] = {}
    
    if payload.name is not None:
        update_kwargs["name"] = payload.name
    
    if payload.description is not None:
        update_kwargs["description"] = payload.description
    
    if payload.columns is not None:
        update_kwargs["columns"] = [
            ReportColumn(
                field=c.field,
                label=c.label,
                visible=c.visible,
                sort_order=c.sort_order,
                sort_direction=c.sort_direction,
                aggregate=c.aggregate,
                format=c.format,
            )
            for c in payload.columns
        ]
    
    if payload.filters is not None:
        update_kwargs["filters"] = [
            ReportFilter(
                field=f.field,
                operator=FilterOperator(f.operator),
                value=f.value,
                value2=f.value2,
            )
            for f in payload.filters
        ]
    
    if payload.group_by is not None:
        update_kwargs["group_by"] = payload.group_by
    
    if payload.default_format is not None:
        update_kwargs["default_format"] = ReportFormat(payload.default_format)
    
    if payload.schedule is not None:
        update_kwargs["schedule"] = ReportSchedule(
            frequency=ScheduleFrequency(payload.schedule.frequency),
            day_of_week=payload.schedule.day_of_week,
            day_of_month=payload.schedule.day_of_month,
            time_of_day=payload.schedule.time_of_day,
            timezone=payload.schedule.timezone,
            recipients=payload.schedule.recipients,
            enabled=payload.schedule.enabled,
        )
    
    if payload.is_public is not None:
        update_kwargs["is_public"] = payload.is_public
    
    expected_version = definition.version
    definition.update(**update_kwargs)
    
    await repo.update(definition, expected_version)
    
    return _definition_to_response(definition)


@router.delete("/definitions/{definition_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_report_definition(
    definition_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> None:
    """Delete a custom report definition."""
    repo = SqlAlchemyReportDefinitionRepository(session)
    deleted = await repo.delete(definition_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report definition {definition_id} not found",
        )


@router.post("/definitions/{definition_id}/generate", response_model=GenerateReportResponse)
async def generate_custom_report(
    definition_id: str,
    payload: GenerateReportRequest | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> GenerateReportResponse:
    """Generate a report from a custom definition."""
    definition_repo = SqlAlchemyReportDefinitionRepository(session)
    execution_repo = SqlAlchemyReportExecutionRepository(session)
    data_provider = SqlAlchemyReportDataProvider(session)
    
    use_case = GenerateReportUseCase(
        definition_repo=definition_repo,
        execution_repo=execution_repo,
        report_data_provider=data_provider,
    )
    
    command = GenerateReportCommand(
        definition_id=definition_id,
        format=payload.format if payload else None,
        parameters=payload.parameters if payload else None,
        requested_by=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    
    result = await use_case.execute(command)
    
    return GenerateReportResponse(
        execution_id=result.execution_id,
        status=result.status.value,
        format=result.format.value,
        row_count=result.row_count,
        download_url=f"/api/v1/reports/executions/{result.execution_id}/download" if result.status.value == "completed" else None,
    )


@router.get("/executions/{execution_id}", response_model=ReportExecutionResponse)
async def get_report_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> ReportExecutionResponse:
    """Get a report execution status."""
    repo = SqlAlchemyReportExecutionRepository(session)
    execution = await repo.get_by_id(execution_id)
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report execution {execution_id} not found",
        )
    
    return ReportExecutionResponse(
        id=execution.id,
        report_definition_id=execution.report_definition_id,
        status=execution.status.value,
        format=execution.format.value,
        parameters=execution.parameters,
        result_path=execution.result_path,
        row_count=execution.row_count,
        error_message=execution.error_message,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        created_at=execution.created_at,
        requested_by=execution.requested_by,
    )


@router.get("/executions/{execution_id}/download")
async def download_report(
    execution_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> Response:
    """Download a generated report."""
    repo = SqlAlchemyReportExecutionRepository(session)
    execution = await repo.get_by_id(execution_id)
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report execution {execution_id} not found",
        )
    
    if execution.status.value != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report generation not completed",
        )
    
    # In production, fetch from file storage
    content_types = {
        "json": "application/json",
        "csv": "text/csv",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    
    return Response(
        content=b"{}",
        media_type=content_types.get(execution.format.value, "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="report_{execution_id}.{execution.format.value}"'
        },
    )


# ===============================
# Legacy Celery-based Report Endpoints
# ===============================


@router.post("/sales", response_model=dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
async def generate_sales_report_endpoint(
    start_date: date = Query(..., description="Report start date"),
    end_date: date = Query(..., description="Report end date"),
    email_to: str | None = Query(None, description="Email recipient (optional)"),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> dict[str, Any]:
    """
    Generate sales report for date range.
    
    Returns task_id for tracking. Optionally emails report when complete.
    """
    # Schedule report generation
    task = generate_sales_report.apply_async(
        args=[start_date.isoformat(), end_date.isoformat(), "json"],
        queue="reports",
    )
    
    # If email requested, chain email task
    if email_to:
        # Chain: generate report -> send email
        task.then(
            send_report_email.s(email_to, "sales")
        )
    
    return {
        "task_id": task.id,
        "status": "queued",
        "message": "Report generation started",
        "email_notification": bool(email_to),
    }


@router.post("/inventory", response_model=dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
async def generate_inventory_report_endpoint(
    email_to: str | None = Query(None, description="Email recipient (optional)"),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> dict[str, Any]:
    """
    Generate current inventory report.
    
    Returns task_id for tracking. Optionally emails report when complete.
    """
    # Schedule report generation
    task = generate_inventory_report.apply_async(queue="reports")
    
    # If email requested, chain email task
    if email_to:
        task.then(
            send_report_email.s(email_to, "inventory")
        )
    
    return {
        "task_id": task.id,
        "status": "queued",
        "message": "Report generation started",
        "email_notification": bool(email_to),
    }


@router.get("/task/{task_id}", response_model=dict[str, Any])
async def get_report_task_status(
    task_id: str,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> dict[str, Any]:
    """Get status of a report generation task."""
    result = AsyncResult(task_id, app=celery_app)
    
    response: dict[str, Any] = {
        "task_id": task_id,
        "state": result.state,
        "result": None,
        "error": None,
    }
    
    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.info)
    
    return response
