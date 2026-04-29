"""Analytics dashboard router for advanced reporting metrics."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import MANAGEMENT_ROLES, require_roles
from app.domain.auth.entities import User
from app.infrastructure.db.models.customer_model import CustomerModel
from app.infrastructure.db.models.inventory_movement_model import InventoryMovementModel
from app.infrastructure.db.models.product_model import ProductModel
from app.infrastructure.db.models.sale_model import SaleItemModel, SaleModel
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/analytics", tags=["Analytics Dashboard"])


# ============================
# Response Schemas
# ============================


class SalesTrendPoint(BaseModel):
    """A single point in sales trend data."""
    period: str = Field(..., description="Period label (date, week, month)")
    total_sales: int = Field(..., description="Number of sales")
    total_revenue: float = Field(..., description="Total revenue amount")
    avg_sale_amount: float = Field(..., description="Average sale amount")


class SalesTrendsResponse(BaseModel):
    """Sales trends over time."""
    period_type: str = Field(..., description="Type of period (daily, weekly, monthly)")
    data: list[SalesTrendPoint] = Field(..., description="Trend data points")
    summary: dict[str, Any] = Field(..., description="Summary statistics")


class TopProductItem(BaseModel):
    """Top selling product."""
    product_id: str
    product_name: str
    sku: str
    quantity_sold: int
    revenue: float
    profit_margin: float | None = None


class TopProductsResponse(BaseModel):
    """Top products response."""
    period: str
    products: list[TopProductItem]


class InventoryTurnoverItem(BaseModel):
    """Inventory turnover for a product."""
    product_id: str
    product_name: str
    sku: str
    current_stock: int
    units_sold: int
    turnover_rate: float = Field(..., description="Units sold / avg inventory")
    days_to_sell: float | None = Field(None, description="Avg days to sell through inventory")


class InventoryTurnoverResponse(BaseModel):
    """Inventory turnover metrics."""
    period: str
    items: list[InventoryTurnoverItem]
    summary: dict[str, Any]


class EmployeePerformanceItem(BaseModel):
    """Employee performance metrics."""
    employee_id: str
    employee_name: str
    total_sales: int
    total_revenue: float
    avg_sale_amount: float
    items_sold: int


class EmployeePerformanceResponse(BaseModel):
    """Employee performance response."""
    period: str
    employees: list[EmployeePerformanceItem]
    summary: dict[str, Any]


class CustomerAnalyticsResponse(BaseModel):
    """Customer analytics summary."""
    total_customers: int
    new_customers_period: int
    returning_customers: int
    avg_customer_value: float
    top_customers: list[dict[str, Any]]


class DashboardSummaryResponse(BaseModel):
    """Complete dashboard summary."""
    period: str
    sales: dict[str, Any]
    inventory: dict[str, Any]
    customers: dict[str, Any]
    trends: dict[str, Any]


# ============================
# Endpoints
# ============================


@router.get("/sales/trends", response_model=SalesTrendsResponse)
async def get_sales_trends(
    period_type: Annotated[str, Query(description="Period type: daily, weekly, monthly")] = "daily",
    start_date: Annotated[datetime | None, Query(description="Start date for analysis")] = None,
    end_date: Annotated[datetime | None, Query(description="End date for analysis")] = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> SalesTrendsResponse:
    """
    Get sales trends over time.
    
    Returns aggregated sales data grouped by the specified period type.
    """
    # Default to last 30 days
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build period grouping based on period_type
    if period_type == "weekly":
        period_expr = func.date_trunc("week", SaleModel.created_at)
    elif period_type == "monthly":
        period_expr = func.date_trunc("month", SaleModel.created_at)
    else:  # daily
        period_expr = func.date_trunc("day", SaleModel.created_at)
    
    stmt = (
        select(
            period_expr.label("period"),
            func.count(SaleModel.id).label("total_sales"),
            func.coalesce(func.sum(SaleModel.total_amount), 0).label("total_revenue"),
            func.coalesce(func.avg(SaleModel.total_amount), 0).label("avg_sale_amount"),
        )
        .where(SaleModel.created_at >= start_date)
        .where(SaleModel.created_at <= end_date)
        .where(SaleModel.status == "completed")
        .group_by(period_expr)
        .order_by(period_expr.asc())
    )
    
    result = await session.execute(stmt)
    rows = result.all()
    
    data = [
        SalesTrendPoint(
            period=row.period.strftime("%Y-%m-%d") if row.period else "",
            total_sales=int(row.total_sales or 0),
            total_revenue=float(row.total_revenue or 0),
            avg_sale_amount=float(row.avg_sale_amount or 0),
        )
        for row in rows
    ]
    
    # Calculate summary
    total_revenue = sum(d.total_revenue for d in data)
    total_sales = sum(d.total_sales for d in data)
    
    return SalesTrendsResponse(
        period_type=period_type,
        data=data,
        summary={
            "total_revenue": total_revenue,
            "total_sales": total_sales,
            "avg_daily_revenue": total_revenue / max(len(data), 1),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
        },
    )


@router.get("/sales/top-products", response_model=TopProductsResponse)
async def get_top_products(
    limit: Annotated[int, Query(ge=1, le=100, description="Number of products to return")] = 10,
    start_date: Annotated[datetime | None, Query(description="Start date for analysis")] = None,
    end_date: Annotated[datetime | None, Query(description="End date for analysis")] = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> TopProductsResponse:
    """
    Get top selling products by revenue.
    """
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    stmt = (
        select(
            ProductModel.id,
            ProductModel.name,
            ProductModel.sku,
            func.coalesce(func.sum(SaleItemModel.quantity), 0).label("quantity_sold"),
            func.coalesce(func.sum(SaleItemModel.total_price), 0).label("revenue"),
            ProductModel.price_retail,
            ProductModel.purchase_price,
        )
        .join(SaleItemModel, ProductModel.id == SaleItemModel.product_id)
        .join(SaleModel, SaleItemModel.sale_id == SaleModel.id)
        .where(SaleModel.created_at >= start_date)
        .where(SaleModel.created_at <= end_date)
        .where(SaleModel.status == "completed")
        .group_by(
            ProductModel.id,
            ProductModel.name,
            ProductModel.sku,
            ProductModel.price_retail,
            ProductModel.purchase_price,
        )
        .order_by(func.sum(SaleItemModel.total_price).desc())
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    rows = result.all()
    
    products = []
    for row in rows:
        profit_margin = None
        if row.purchase_price and row.price_retail and row.price_retail > 0:
            profit_margin = float((row.price_retail - row.purchase_price) / row.price_retail * 100)
        
        products.append(TopProductItem(
            product_id=row.id,
            product_name=row.name,
            sku=row.sku,
            quantity_sold=int(row.quantity_sold),
            revenue=float(row.revenue),
            profit_margin=profit_margin,
        ))
    
    return TopProductsResponse(
        period=f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        products=products,
    )


@router.get("/inventory/turnover", response_model=InventoryTurnoverResponse)
async def get_inventory_turnover(
    limit: Annotated[int, Query(ge=1, le=100, description="Number of products to return")] = 20,
    start_date: Annotated[datetime | None, Query(description="Start date for analysis")] = None,
    end_date: Annotated[datetime | None, Query(description="End date for analysis")] = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> InventoryTurnoverResponse:
    """
    Get inventory turnover metrics for products.
    
    Turnover rate = Units sold / Average inventory
    Higher turnover indicates faster-selling products.
    """
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    days_in_period = (end_date - start_date).days or 1
    
    # Get current stock levels from inventory movements
    stock_subq = (
        select(
            InventoryMovementModel.product_id,
            func.sum(
                case(
                    (InventoryMovementModel.direction == "IN", InventoryMovementModel.quantity),
                    else_=-InventoryMovementModel.quantity,
                )
            ).label("current_stock"),
        )
        .group_by(InventoryMovementModel.product_id)
        .subquery()
    )
    
    # Get sales data
    sales_subq = (
        select(
            SaleItemModel.product_id,
            func.sum(SaleItemModel.quantity).label("units_sold"),
        )
        .join(SaleModel, SaleItemModel.sale_id == SaleModel.id)
        .where(SaleModel.created_at >= start_date)
        .where(SaleModel.created_at <= end_date)
        .where(SaleModel.status == "completed")
        .group_by(SaleItemModel.product_id)
        .subquery()
    )
    
    stmt = (
        select(
            ProductModel.id,
            ProductModel.name,
            ProductModel.sku,
            func.coalesce(stock_subq.c.current_stock, 0).label("current_stock"),
            func.coalesce(sales_subq.c.units_sold, 0).label("units_sold"),
        )
        .outerjoin(stock_subq, ProductModel.id == stock_subq.c.product_id)
        .outerjoin(sales_subq, ProductModel.id == sales_subq.c.product_id)
        .where(ProductModel.is_active == True)  # noqa: E712
        .order_by(func.coalesce(sales_subq.c.units_sold, 0).desc())
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    rows = result.all()
    
    items = []
    total_turnover = 0.0
    
    for row in rows:
        current_stock = int(row.current_stock or 0)
        units_sold = int(row.units_sold or 0)
        
        # Calculate turnover rate (annualized)
        # Avg inventory = (beginning + ending) / 2, approximated as current + sold/2
        avg_inventory = max((current_stock + units_sold / 2), 1)
        turnover_rate = units_sold / avg_inventory
        
        # Days to sell current stock (if any sales)
        days_to_sell = None
        if units_sold > 0 and current_stock > 0:
            daily_sales = units_sold / days_in_period
            days_to_sell = current_stock / daily_sales if daily_sales > 0 else None
        
        items.append(InventoryTurnoverItem(
            product_id=row.id,
            product_name=row.name,
            sku=row.sku,
            current_stock=current_stock,
            units_sold=units_sold,
            turnover_rate=round(turnover_rate, 2),
            days_to_sell=round(days_to_sell, 1) if days_to_sell else None,
        ))
        
        total_turnover += turnover_rate
    
    return InventoryTurnoverResponse(
        period=f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        items=items,
        summary={
            "avg_turnover_rate": round(total_turnover / max(len(items), 1), 2),
            "total_products_analyzed": len(items),
            "period_days": days_in_period,
        },
    )


@router.get("/employees/performance", response_model=EmployeePerformanceResponse)
async def get_employee_performance(
    limit: Annotated[int, Query(ge=1, le=100, description="Number of employees to return")] = 20,
    start_date: Annotated[datetime | None, Query(description="Start date for analysis")] = None,
    end_date: Annotated[datetime | None, Query(description="End date for analysis")] = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> EmployeePerformanceResponse:
    """
    Get employee performance metrics based on sales.
    """
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Note: This assumes cashier_id in sales relates to employees
    # In practice, you may need to join through users table
    stmt = (
        select(
            SaleModel.cashier_id.label("employee_id"),
            func.count(SaleModel.id).label("total_sales"),
            func.coalesce(func.sum(SaleModel.total_amount), 0).label("total_revenue"),
            func.coalesce(func.avg(SaleModel.total_amount), 0).label("avg_sale_amount"),
        )
        .where(SaleModel.created_at >= start_date)
        .where(SaleModel.created_at <= end_date)
        .where(SaleModel.status == "completed")
        .where(SaleModel.cashier_id != None)  # noqa: E711
        .group_by(SaleModel.cashier_id)
        .order_by(func.sum(SaleModel.total_amount).desc())
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    rows = result.all()
    
    # Get items sold per cashier
    items_stmt = (
        select(
            SaleModel.cashier_id,
            func.coalesce(func.sum(SaleItemModel.quantity), 0).label("items_sold"),
        )
        .join(SaleItemModel, SaleModel.id == SaleItemModel.sale_id)
        .where(SaleModel.created_at >= start_date)
        .where(SaleModel.created_at <= end_date)
        .where(SaleModel.status == "completed")
        .group_by(SaleModel.cashier_id)
    )
    items_result = await session.execute(items_stmt)
    items_by_cashier = {r.cashier_id: int(r.items_sold) for r in items_result.all()}
    
    employees = []
    total_revenue = 0.0
    total_sales = 0
    
    for row in rows:
        revenue = float(row.total_revenue or 0)
        sales_count = int(row.total_sales or 0)
        
        employees.append(EmployeePerformanceItem(
            employee_id=row.employee_id or "unknown",
            employee_name=f"Employee {row.employee_id[:8] if row.employee_id else 'Unknown'}",
            total_sales=sales_count,
            total_revenue=revenue,
            avg_sale_amount=float(row.avg_sale_amount or 0),
            items_sold=items_by_cashier.get(row.employee_id, 0),
        ))
        
        total_revenue += revenue
        total_sales += sales_count
    
    return EmployeePerformanceResponse(
        period=f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        employees=employees,
        summary={
            "total_revenue": total_revenue,
            "total_sales": total_sales,
            "avg_revenue_per_employee": total_revenue / max(len(employees), 1),
            "total_employees_with_sales": len(employees),
        },
    )


@router.get("/customers", response_model=CustomerAnalyticsResponse)
async def get_customer_analytics(
    start_date: Annotated[datetime | None, Query(description="Start date for analysis")] = None,
    end_date: Annotated[datetime | None, Query(description="End date for analysis")] = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> CustomerAnalyticsResponse:
    """
    Get customer analytics summary.
    """
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Total customers
    total_stmt = select(func.count(CustomerModel.id))
    total_result = await session.execute(total_stmt)
    total_customers = total_result.scalar() or 0
    
    # New customers in period
    new_stmt = (
        select(func.count(CustomerModel.id))
        .where(CustomerModel.created_at >= start_date)
        .where(CustomerModel.created_at <= end_date)
    )
    new_result = await session.execute(new_stmt)
    new_customers = new_result.scalar() or 0
    
    # Customers with purchases in period (returning)
    returning_stmt = (
        select(func.count(func.distinct(SaleModel.customer_id)))
        .where(SaleModel.created_at >= start_date)
        .where(SaleModel.created_at <= end_date)
        .where(SaleModel.customer_id != None)  # noqa: E711
    )
    returning_result = await session.execute(returning_stmt)
    returning_customers = returning_result.scalar() or 0
    
    # Average customer value
    avg_stmt = select(func.avg(CustomerModel.total_purchases))
    avg_result = await session.execute(avg_stmt)
    avg_customer_value = float(avg_result.scalar() or 0)
    
    # Top customers by total purchases
    top_stmt = (
        select(
            CustomerModel.id,
            CustomerModel.name,
            CustomerModel.email,
            CustomerModel.total_purchases,
            CustomerModel.loyalty_points,
        )
        .order_by(CustomerModel.total_purchases.desc())
        .limit(10)
    )
    top_result = await session.execute(top_stmt)
    top_customers = [
        {
            "id": row.id,
            "name": row.name,
            "email": row.email,
            "total_purchases": float(row.total_purchases or 0),
            "loyalty_points": row.loyalty_points,
        }
        for row in top_result.all()
    ]
    
    return CustomerAnalyticsResponse(
        total_customers=total_customers,
        new_customers_period=new_customers,
        returning_customers=returning_customers,
        avg_customer_value=avg_customer_value,
        top_customers=top_customers,
    )


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    start_date: Annotated[datetime | None, Query(description="Start date for analysis")] = None,
    end_date: Annotated[datetime | None, Query(description="End date for analysis")] = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> DashboardSummaryResponse:
    """
    Get comprehensive dashboard summary with key metrics.
    """
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Previous period for comparison
    period_length = (end_date - start_date).days
    prev_start = start_date - timedelta(days=period_length)
    prev_end = start_date
    
    # Current period sales
    current_sales_stmt = (
        select(
            func.count(SaleModel.id).label("count"),
            func.coalesce(func.sum(SaleModel.total_amount), 0).label("revenue"),
        )
        .where(SaleModel.created_at >= start_date)
        .where(SaleModel.created_at <= end_date)
        .where(SaleModel.status == "completed")
    )
    current_sales = (await session.execute(current_sales_stmt)).one()
    
    # Previous period sales
    prev_sales_stmt = (
        select(
            func.count(SaleModel.id).label("count"),
            func.coalesce(func.sum(SaleModel.total_amount), 0).label("revenue"),
        )
        .where(SaleModel.created_at >= prev_start)
        .where(SaleModel.created_at < prev_end)
        .where(SaleModel.status == "completed")
    )
    prev_sales = (await session.execute(prev_sales_stmt)).one()
    
    # Calculate growth
    revenue_growth = 0.0
    if prev_sales.revenue and float(prev_sales.revenue) > 0:
        revenue_growth = ((float(current_sales.revenue) - float(prev_sales.revenue)) / float(prev_sales.revenue)) * 100
    
    # Inventory summary
    active_products_stmt = select(func.count(ProductModel.id)).where(ProductModel.is_active == True)  # noqa: E712
    active_products = (await session.execute(active_products_stmt)).scalar() or 0
    
    # Customer summary
    total_customers_stmt = select(func.count(CustomerModel.id))
    total_customers = (await session.execute(total_customers_stmt)).scalar() or 0
    
    new_customers_stmt = (
        select(func.count(CustomerModel.id))
        .where(CustomerModel.created_at >= start_date)
    )
    new_customers = (await session.execute(new_customers_stmt)).scalar() or 0
    
    return DashboardSummaryResponse(
        period=f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        sales={
            "total_sales": int(current_sales.count or 0),
            "total_revenue": float(current_sales.revenue or 0),
            "revenue_growth_pct": round(revenue_growth, 1),
            "avg_sale_amount": float(current_sales.revenue or 0) / max(int(current_sales.count or 1), 1),
        },
        inventory={
            "active_products": active_products,
        },
        customers={
            "total_customers": total_customers,
            "new_customers": new_customers,
        },
        trends={
            "previous_period_revenue": float(prev_sales.revenue or 0),
            "period_comparison": "up" if revenue_growth > 0 else ("down" if revenue_growth < 0 else "flat"),
        },
    )
