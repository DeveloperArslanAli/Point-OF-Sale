from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    INVENTORY_ROLES,
    MANAGEMENT_ROLES,
    SALES_ROLES,
    require_roles,
)
from app.api.dependencies.cache import get_cache_service
from app.application.common.cache import CacheService
from app.api.schemas.inventory import (
    InventoryMovementCreate,
    InventoryMovementListOut,
    InventoryMovementOut,
    InventoryMovementPageMetaOut,
    InventoryMovementRecordOut,
    StockLevelOut,
)
from app.api.schemas.product import ProductCreate, ProductDeactivate, ProductOut, ProductUpdate
from app.api.schemas.product_import import (
    ProductImportItemOut,
    ProductImportJobDetailOut,
    ProductImportJobItemsPageMetaOut,
    ProductImportJobListOut,
    ProductImportJobOut,
    ProductImportJobPageMetaOut,
    ProductImportJobStatusOut,
)
from app.application.catalog.services.import_scheduler import ImmediateImportScheduler
from app.infrastructure.adapters.celery_import_scheduler import CeleryImportScheduler
from app.application.catalog.use_cases.create_product import (
    CreateProductInput,
    CreateProductUseCase,
)
from app.application.catalog.use_cases.deactivate_product import (
    DeactivateProductInput,
    DeactivateProductUseCase,
)
from app.application.catalog.use_cases.get_product_import_job import (
    GetProductImportJobInput,
    GetProductImportJobUseCase,
)
from app.application.catalog.use_cases.get_product_import_job_items import (
    GetProductImportJobItemsInput,
    GetProductImportJobItemsUseCase,
)
from app.application.catalog.use_cases.get_product_import_status import (
    GetProductImportStatusUseCase,
)
from app.application.catalog.use_cases.list_product_import_jobs import (
    ListProductImportJobsInput,
    ListProductImportJobsUseCase,
)
from app.application.catalog.use_cases.list_products import (
    ListProductsInput,
    ListProductsUseCase,
)
from app.application.catalog.use_cases.process_product_import_job import (
    ProcessProductImportJobUseCase,
)
from app.application.catalog.use_cases.queue_product_import import (
    QueueProductImportInput,
    QueueProductImportResult,
    QueueProductImportUseCase,
)
from app.application.catalog.use_cases.retry_product_import_job import (
    RetryProductImportJobInput,
    RetryProductImportJobUseCase,
)
from app.core.settings import get_settings
from app.application.catalog.use_cases.update_product import (
    UpdateProductInput,
    UpdateProductUseCase,
)
from app.application.inventory.use_cases.get_product_stock import (
    GetProductStockInput,
    GetProductStockUseCase,
)
from app.application.inventory.use_cases.list_inventory_movements import (
    ListInventoryMovementsInput,
    ListInventoryMovementsUseCase,
)
from app.application.inventory.use_cases.record_inventory_movement import (
    RecordInventoryMovementInput,
    RecordInventoryMovementUseCase,
)
from app.domain.auth.entities import User
from app.domain.catalog.import_job import ImportStatus
from app.domain.common.errors import ValidationError
from app.infrastructure.db.repositories.category_repository import SqlAlchemyCategoryRepository
from app.infrastructure.db.repositories.inventory_movement_repository import (
    SqlAlchemyInventoryMovementRepository,
)
from app.infrastructure.db.repositories.inventory_repository import SqlAlchemyProductRepository
from app.infrastructure.db.repositories.product_import_repository import (
    SqlAlchemyProductImportJobRepository,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.websocket.handlers.inventory_handler import InventoryEventHandler
from app.infrastructure.websocket.events import WebSocketEvent, EventType, PriceChangeEvent
from app.infrastructure.websocket.event_dispatcher import get_event_dispatcher
from app.shared.pagination import Page, PageParams

settings = get_settings()


def _use_celery_imports() -> bool:
    override = os.getenv("USE_CELERY_IMPORTS")
    if override is not None:
        return override.lower() in {"1", "true", "yes", "on"}
    return settings.ENV in {"staging", "prod"}


def _build_import_scheduler(
    job_repo: SqlAlchemyProductImportJobRepository,
    product_repo: SqlAlchemyProductRepository,
    category_repo: SqlAlchemyCategoryRepository,
):
    if _use_celery_imports():
        return CeleryImportScheduler()
    processor = ProcessProductImportJobUseCase(job_repo, product_repo, category_repo)
    return ImmediateImportScheduler(processor)


router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_session),
    cache: CacheService = Depends(get_cache_service),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> ProductOut:
    repo = SqlAlchemyProductRepository(session)
    use_case = CreateProductUseCase(repo)
    product = await use_case.execute(
        CreateProductInput(
            name=payload.name,
            sku=payload.sku,
            retail_price=payload.retail_price,
            purchase_price=payload.purchase_price,
            currency=payload.currency,
            category_id=payload.category_id,
        )
    )
    await cache.clear_prefix("products:list")
    return ProductOut(
        id=product.id,
        name=product.name,
        sku=product.sku,
        retail_price=product.price_retail.amount,
        purchase_price=product.purchase_price.amount,
        category_id=product.category_id,
        active=product.active,
        version=product.version,
    )


def _field_set(model: object) -> set[str]:
    return set(
        getattr(model, "model_fields_set", None)
        or getattr(model, "__fields_set__", None)
        or []
    )


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    session: AsyncSession = Depends(get_session),
    cache: CacheService = Depends(get_cache_service),
    current_user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> ProductOut:
    provided = _field_set(payload)
    update_fields = provided - {"expected_version"}
    if not update_fields:
        raise ValidationError("No update fields provided")

    repo = SqlAlchemyProductRepository(session)
    
    # Get old product for price change detection
    old_product = await repo.get_by_id(product_id)
    if not old_product:
        raise ValidationError("Product not found")
    
    use_case = UpdateProductUseCase(repo)
    product = await use_case.execute(
        UpdateProductInput(
            product_id=product_id,
            expected_version=payload.expected_version,
            name=payload.name if "name" in provided else None,
            retail_price=payload.retail_price if "retail_price" in provided else None,
            purchase_price=payload.purchase_price if "purchase_price" in provided else None,
            category_id=payload.category_id if "category_id" in provided else None,
            category_id_provided="category_id" in provided,
        )
    )
    await cache.clear_prefix("products:list")
    
    # Publish price change event if retail price changed
    if "retail_price" in provided and payload.retail_price != old_product.price_retail.amount:
        try:
            dispatcher = get_event_dispatcher()
            price_event = PriceChangeEvent(
                product_id=str(product.id),
                product_name=product.name,
                old_price=old_product.price_retail.amount,
                new_price=product.price_retail.amount,
                changed_by=current_user.username,
                reason="Manual update",
            )
            event = WebSocketEvent(
                type=EventType.PRICE_CHANGED,
                tenant_id=getattr(current_user, "tenant_id", "default"),
                payload=price_event.model_dump(),
            )
            await dispatcher.publish_event(
                event,
                tenant_id=getattr(current_user, "tenant_id", "default"),
            )
        except Exception as e:
            # Don't fail the request if event publishing fails
            import structlog
            logger = structlog.get_logger(__name__)
            logger.error("price_change_event_failed", error=str(e))
    
    return ProductOut(
        id=product.id,
        name=product.name,
        sku=product.sku,
        retail_price=product.price_retail.amount,
        purchase_price=product.purchase_price.amount,
        category_id=product.category_id,
        active=product.active,
        version=product.version,
    )


@router.post("/{product_id}/deactivate", response_model=ProductOut)
async def deactivate_product(
    product_id: str,
    payload: ProductDeactivate,
    session: AsyncSession = Depends(get_session),
    cache: CacheService = Depends(get_cache_service),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> ProductOut:
    repo = SqlAlchemyProductRepository(session)
    use_case = DeactivateProductUseCase(repo)
    product = await use_case.execute(
        DeactivateProductInput(
            product_id=product_id,
            expected_version=payload.expected_version,
        )
    )
    await cache.clear_prefix("products:list")
    return ProductOut(
        id=product.id,
        name=product.name,
        sku=product.sku,
        retail_price=product.price_retail.amount,
        purchase_price=product.purchase_price.amount,
        category_id=product.category_id,
        active=product.active,
        version=product.version,
    )


@router.get("", response_model=dict)
async def list_products(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    category_id: str | None = None,
    active: bool | None = None,
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    sort_by: str = Query("created_at"),
    sort_direction: str = Query("desc"),
    session: AsyncSession = Depends(get_session),
    cache: CacheService = Depends(get_cache_service),
    _: User = Depends(require_roles(*SALES_ROLES)),
) -> dict[str, Any]:
    cache_key = f"products:list:{page}:{limit}:{search}:{category_id}:{active}:{min_price}:{max_price}:{sort_by}:{sort_direction}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    params = PageParams(page=page, limit=limit)
    repo = SqlAlchemyProductRepository(session)
    use_case = ListProductsUseCase(repo)
    result = await use_case.execute(
        ListProductsInput(
            page=params.page,
            limit=params.limit,
            search=search,
            category_id=category_id,
            active=active,
            min_price=min_price,
            max_price=max_price,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
    )

    # Fetch stock levels
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    product_ids = [p.id for p in result.products]
    stock_levels = await inventory_repo.get_stock_levels(product_ids)

    items = [
        {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "retail_price": str(p.price_retail.amount),
            "purchase_price": str(p.purchase_price.amount),
            "category_id": p.category_id,
            "active": p.active,
            "version": p.version,
            "stock_quantity": stock_levels.get(p.id, 0),
        }
        for p in result.products
    ]
    page_obj = Page.build(items, result.total, params)
    response = {"items": page_obj.items, "meta": page_obj.meta.model_dump()}
    await cache.set(cache_key, response, ttl=300)
    return response


@router.post("/import", response_model=ProductImportJobOut, status_code=status.HTTP_202_ACCEPTED)
async def queue_product_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> ProductImportJobOut:
    if file.content_type not in {"text/csv", "application/vnd.ms-excel", None}:
        raise ValidationError("File must be a CSV upload")
    content = await file.read()
    if not content:
        raise ValidationError("Uploaded file is empty")

    product_repo = SqlAlchemyProductRepository(session)
    category_repo = SqlAlchemyCategoryRepository(session)
    job_repo = SqlAlchemyProductImportJobRepository(session)

    scheduler = _build_import_scheduler(job_repo, product_repo, category_repo)

    use_case = QueueProductImportUseCase(job_repo, product_repo, category_repo, scheduler)
    result: QueueProductImportResult = await use_case.execute(
        QueueProductImportInput(filename=file.filename or "import.csv", content=content)
    )
    
    # Build response with task_id for tracking
    job_out = ProductImportJobOut.model_validate(result.job)
    job_out.task_id = result.task_id
    return job_out


@router.post(
    "/{product_id}/inventory/movements",
    response_model=InventoryMovementRecordOut,
    status_code=status.HTTP_201_CREATED,
)
async def record_inventory_movement(
    product_id: str,
    payload: InventoryMovementCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> InventoryMovementRecordOut:
    product_repo = SqlAlchemyProductRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    use_case = RecordInventoryMovementUseCase(product_repo, inventory_repo)
    result = await use_case.execute(
        RecordInventoryMovementInput(
            product_id=product_id,
            quantity=payload.quantity,
            direction=payload.direction,
            reason=payload.reason,
            reference=payload.reference,
            occurred_at=payload.occurred_at,
        )
    )
    movement_out = InventoryMovementOut.model_validate(result.movement)
    stock_out = StockLevelOut.model_validate(result.stock_level)
    return InventoryMovementRecordOut(movement=movement_out, stock=stock_out)


@router.get("/{product_id}/inventory/movements", response_model=InventoryMovementListOut)
async def list_inventory_movements(
    product_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> InventoryMovementListOut:
    params = PageParams(page=page, limit=limit)
    product_repo = SqlAlchemyProductRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    use_case = ListInventoryMovementsUseCase(product_repo, inventory_repo)
    result = await use_case.execute(
        ListInventoryMovementsInput(
            product_id=product_id,
            page=params.page,
            limit=params.limit,
        )
    )
    items_out = [InventoryMovementOut.model_validate(movement) for movement in result.movements]
    meta_out = InventoryMovementPageMetaOut(
        page=result.page,
        limit=result.limit,
        total=result.total,
        pages=result.pages,
    )
    return InventoryMovementListOut(items=items_out, meta=meta_out)


@router.get("/{product_id}/stock", response_model=StockLevelOut)
async def get_product_stock(
    product_id: str,
    as_of: datetime | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*SALES_ROLES)),
) -> StockLevelOut:
    product_repo = SqlAlchemyProductRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    use_case = GetProductStockUseCase(product_repo, inventory_repo)
    stock = await use_case.execute(GetProductStockInput(product_id=product_id, as_of=as_of))
    return StockLevelOut.model_validate(stock)


@router.get("/import", response_model=ProductImportJobListOut)
async def list_product_import_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: ImportStatus | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> ProductImportJobListOut:
    params = PageParams(page=page, limit=limit)
    repo = SqlAlchemyProductImportJobRepository(session)
    use_case = ListProductImportJobsUseCase(repo)
    result = await use_case.execute(
        ListProductImportJobsInput(page=params.page, limit=params.limit, status=status)
    )
    items = [ProductImportJobOut.model_validate(job) for job in result.jobs]
    page_obj = Page.build(items, result.total, params)
    meta_out = ProductImportJobPageMetaOut(**page_obj.meta.model_dump())
    return ProductImportJobListOut(items=items, meta=meta_out)


@router.get("/import/status", response_model=ProductImportJobStatusOut)
async def get_product_import_status(
    limit: int = Query(5, ge=0, le=50),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> ProductImportJobStatusOut:
    repo = SqlAlchemyProductImportJobRepository(session)
    use_case = GetProductImportStatusUseCase(repo)
    summary = await use_case.execute(limit=limit)
    last_jobs = [ProductImportJobOut.model_validate(job) for job in summary.recent_jobs]
    return ProductImportJobStatusOut(
        total_jobs=summary.total_jobs,
        pending=summary.pending,
        queued=summary.queued,
        processing=summary.processing,
        completed=summary.completed,
        failed=summary.failed,
        errors=summary.errors,
        last_jobs=last_jobs,
    )


@router.get("/import/stream", response_class=StreamingResponse)
async def stream_product_import_status(
    poll_interval: float = Query(2.0, ge=0.5, le=30.0),
    limit: int = Query(5, ge=0, le=50),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> StreamingResponse:
    repo = SqlAlchemyProductImportJobRepository(session)
    use_case = GetProductImportStatusUseCase(repo)

    async def event_generator() -> AsyncIterator[str]:
        try:
            while True:
                summary = await use_case.execute(limit=limit)
                last_jobs = [ProductImportJobOut.model_validate(job).model_dump(mode="json") for job in summary.recent_jobs]
                payload = {
                    "total_jobs": summary.total_jobs,
                    "pending": summary.pending,
                    "queued": summary.queued,
                    "processing": summary.processing,
                    "completed": summary.completed,
                    "failed": summary.failed,
                    "errors": summary.errors,
                    "last_jobs": last_jobs,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:  # Client disconnected
            raise

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@router.get("/import/{job_id}", response_model=ProductImportJobOut)
async def get_product_import_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> ProductImportJobOut:
    repo = SqlAlchemyProductImportJobRepository(session)
    use_case = GetProductImportJobUseCase(repo)
    job = await use_case.execute(GetProductImportJobInput(job_id=job_id))
    return ProductImportJobOut.model_validate(job)


@router.get("/import/{job_id}/items", response_model=ProductImportJobDetailOut)
async def get_product_import_job_items(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: ImportStatus | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> ProductImportJobDetailOut:
    repo = SqlAlchemyProductImportJobRepository(session)
    use_case = GetProductImportJobItemsUseCase(repo)
    result = await use_case.execute(
        GetProductImportJobItemsInput(job_id=job_id, page=page, limit=limit, status=status)
    )
    job_out = ProductImportJobOut.model_validate(result.job)
    items_out = [ProductImportItemOut.model_validate(item) for item in result.items]
    meta_out = ProductImportJobItemsPageMetaOut(
        page=result.page,
        limit=result.limit,
        total=result.total,
        pages=result.pages,
    )
    return ProductImportJobDetailOut(**job_out.model_dump(), items=items_out, meta=meta_out)


@router.get("/import/task/{task_id}", response_model=dict[str, Any], status_code=status.HTTP_200_OK)
async def get_import_task_status(
    task_id: str,
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> dict[str, Any]:
    """Get the status of an async import task."""
    if _use_celery_imports():
        scheduler = CeleryImportScheduler()
        return await scheduler.get_task_status(task_id)
    return {"state": "disabled", "result": None, "error": "Celery tracking disabled in this environment"}


@router.post("/import/{job_id}/retry", response_model=ProductImportJobOut, status_code=status.HTTP_202_ACCEPTED)
async def retry_product_import_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> ProductImportJobOut:
    job_repo = SqlAlchemyProductImportJobRepository(session)
    product_repo = SqlAlchemyProductRepository(session)
    category_repo = SqlAlchemyCategoryRepository(session)
    processor = ProcessProductImportJobUseCase(job_repo, product_repo, category_repo)
    scheduler = ImmediateImportScheduler(processor)
    use_case = RetryProductImportJobUseCase(job_repo, scheduler)
    job = await use_case.execute(RetryProductImportJobInput(job_id=job_id))
    return ProductImportJobOut.model_validate(job)
