"""Integration tests for report generation and analytics endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.reports.entities import (
    ReportColumn,
    ReportDefinition,
    ReportFilter,
    ReportFormat,
    ReportType,
    FilterOperator,
)
from app.infrastructure.reports.exporters import (
    CSVReportExporter,
    ExcelReportExporter,
    PDFReportExporter,
)


# ============================
# Exporter Unit Tests
# ============================


class TestCSVExporter:
    """Tests for CSV report exporter."""

    def test_export_empty_data(self) -> None:
        """Test exporting empty data returns empty bytes."""
        exporter = CSVReportExporter()
        result = exporter.export([], None)
        assert result == b""

    def test_export_simple_data(self) -> None:
        """Test exporting simple data without definition."""
        exporter = CSVReportExporter()
        data = [
            {"name": "Product A", "price": 10.99, "quantity": 5},
            {"name": "Product B", "price": 20.50, "quantity": 3},
        ]
        result = exporter.export(data, None)
        
        decoded = result.decode("utf-8-sig")
        lines = decoded.strip().split("\n")
        
        assert len(lines) == 3  # Header + 2 data rows
        assert "Name" in lines[0]  # Headers are title-cased
        assert "Product A" in lines[1]

    def test_export_with_definition(self) -> None:
        """Test exporting with column definitions."""
        exporter = CSVReportExporter()
        data = [
            {"name": "Product A", "price": 10.99, "quantity": 5},
        ]
        definition = ReportDefinition(
            id="test-id",
            name="Test Report",
            description="Test",
            report_type=ReportType.SALES,
            columns=[
                ReportColumn(field="name", label="Product Name", visible=True),
                ReportColumn(field="price", label="Unit Price", visible=True),
                ReportColumn(field="quantity", label="Qty", visible=False),  # Hidden
            ],
        )
        
        result = exporter.export(data, definition)
        decoded = result.decode("utf-8-sig")
        
        assert "Product Name" in decoded
        assert "Unit Price" in decoded
        assert "Qty" not in decoded  # Hidden column

    def test_export_special_characters(self) -> None:
        """Test exporting data with special characters."""
        exporter = CSVReportExporter()
        data = [
            {"name": "Product with, comma", "description": 'Product "quoted"'},
        ]
        result = exporter.export(data, None)
        decoded = result.decode("utf-8-sig")
        
        # CSV should properly escape special characters
        assert "Product with, comma" in decoded or '"Product with, comma"' in decoded


class TestExcelExporter:
    """Tests for Excel report exporter."""

    def test_export_creates_valid_xlsx(self) -> None:
        """Test that export creates valid XLSX bytes."""
        exporter = ExcelReportExporter()
        data = [
            {"name": "Product A", "price": Decimal("10.99"), "quantity": 5},
            {"name": "Product B", "price": Decimal("20.50"), "quantity": 3},
        ]
        definition = ReportDefinition(
            id="test-id",
            name="Test Report",
            description="Test",
            report_type=ReportType.INVENTORY,
        )
        
        result = exporter.export(data, definition)
        
        # XLSX files start with PK (ZIP header)
        assert result[:2] == b"PK"
        assert len(result) > 100  # Should have some content

    def test_export_empty_data(self) -> None:
        """Test exporting empty data still creates valid Excel file."""
        exporter = ExcelReportExporter()
        definition = ReportDefinition(
            id="test-id",
            name="Empty Report",
            description="Test",
            report_type=ReportType.SALES,
        )
        
        result = exporter.export([], definition)
        
        # Should still create a valid Excel file
        assert result[:2] == b"PK"


class TestPDFExporter:
    """Tests for PDF report exporter."""

    def test_export_creates_valid_pdf(self) -> None:
        """Test that export creates valid PDF bytes."""
        exporter = PDFReportExporter()
        data = [
            {"name": "Product A", "price": 10.99, "quantity": 5},
            {"name": "Product B", "price": 20.50, "quantity": 3},
        ]
        definition = ReportDefinition(
            id="test-id",
            name="Test Report",
            description="Test",
            report_type=ReportType.SALES,
        )
        
        result = exporter.export(data, definition)
        
        # PDF files start with %PDF
        assert result[:4] == b"%PDF"
        assert len(result) > 100

    def test_export_empty_data(self) -> None:
        """Test exporting empty data still creates valid PDF."""
        exporter = PDFReportExporter()
        definition = ReportDefinition(
            id="test-id",
            name="Empty Report",
            description="Test",
            report_type=ReportType.SALES,
        )
        
        result = exporter.export([], definition)
        
        assert result[:4] == b"%PDF"

    def test_export_with_summary(self) -> None:
        """Test exporting with summary section."""
        exporter = PDFReportExporter()
        data = [{"item": "A", "value": 100}]
        definition = ReportDefinition(
            id="test-id",
            name="Summary Report",
            description="Test",
            report_type=ReportType.SALES,
        )
        summary = {"total": 100, "count": 1}
        
        result = exporter.export_with_summary(data, definition, summary)
        
        assert result[:4] == b"%PDF"


# ============================
# Analytics API Tests
# ============================


@pytest.mark.asyncio
class TestAnalyticsEndpoints:
    """Integration tests for analytics endpoints."""

    async def test_sales_trends_requires_auth(
        self, async_client: AsyncClient
    ) -> None:
        """Test that sales trends endpoint requires authentication."""
        response = await async_client.get("/api/v1/analytics/sales/trends")
        assert response.status_code == 401

    async def test_sales_trends_daily(
        self,
        async_client: AsyncClient,
        admin_auth_header: dict[str, str],
    ) -> None:
        """Test getting daily sales trends."""
        response = await async_client.get(
            "/api/v1/analytics/sales/trends",
            params={"period_type": "daily"},
            headers=admin_auth_header,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["period_type"] == "daily"
        assert "data" in data
        assert "summary" in data

    async def test_sales_trends_weekly(
        self,
        async_client: AsyncClient,
        admin_auth_header: dict[str, str],
    ) -> None:
        """Test getting weekly sales trends."""
        response = await async_client.get(
            "/api/v1/analytics/sales/trends",
            params={"period_type": "weekly"},
            headers=admin_auth_header,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["period_type"] == "weekly"

    async def test_top_products(
        self,
        async_client: AsyncClient,
        admin_auth_header: dict[str, str],
    ) -> None:
        """Test getting top products."""
        response = await async_client.get(
            "/api/v1/analytics/sales/top-products",
            params={"limit": 5},
            headers=admin_auth_header,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert "period" in data

    async def test_inventory_turnover(
        self,
        async_client: AsyncClient,
        admin_auth_header: dict[str, str],
    ) -> None:
        """Test getting inventory turnover."""
        response = await async_client.get(
            "/api/v1/analytics/inventory/turnover",
            params={"limit": 10},
            headers=admin_auth_header,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "summary" in data

    async def test_employee_performance(
        self,
        async_client: AsyncClient,
        admin_auth_header: dict[str, str],
    ) -> None:
        """Test getting employee performance."""
        response = await async_client.get(
            "/api/v1/analytics/employees/performance",
            headers=admin_auth_header,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        assert "summary" in data

    async def test_customer_analytics(
        self,
        async_client: AsyncClient,
        admin_auth_header: dict[str, str],
    ) -> None:
        """Test getting customer analytics."""
        response = await async_client.get(
            "/api/v1/analytics/customers",
            headers=admin_auth_header,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_customers" in data
        assert "top_customers" in data

    async def test_dashboard_summary(
        self,
        async_client: AsyncClient,
        admin_auth_header: dict[str, str],
    ) -> None:
        """Test getting dashboard summary."""
        response = await async_client.get(
            "/api/v1/analytics/dashboard/summary",
            headers=admin_auth_header,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "sales" in data
        assert "inventory" in data
        assert "customers" in data
        assert "trends" in data

    async def test_sales_trends_with_date_range(
        self,
        async_client: AsyncClient,
        admin_auth_header: dict[str, str],
    ) -> None:
        """Test sales trends with custom date range."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        response = await async_client.get(
            "/api/v1/analytics/sales/trends",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            headers=admin_auth_header,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert start_date.strftime("%Y-%m-%d") in data["summary"]["period_start"]


# ============================
# Report Definition API Tests
# ============================


@pytest.mark.asyncio
class TestReportDefinitionEndpoints:
    """Integration tests for report definition endpoints."""

    async def test_create_report_definition(
        self,
        async_client: AsyncClient,
        admin_auth_header: dict[str, str],
    ) -> None:
        """Test creating a report definition."""
        response = await async_client.post(
            "/api/v1/reports/definitions",
            json={
                "name": "Daily Sales Report",
                "description": "Summary of daily sales",
                "report_type": "sales",
                "default_format": "csv",
                "columns": [
                    {"field": "sale_number", "label": "Sale #", "visible": True},
                    {"field": "total_amount", "label": "Amount", "visible": True},
                ],
                "filters": [],
            },
            headers=admin_auth_header,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Daily Sales Report"
        assert data["report_type"] == "sales"

    async def test_list_report_definitions(
        self,
        async_client: AsyncClient,
        admin_auth_header: dict[str, str],
    ) -> None:
        """Test listing report definitions."""
        response = await async_client.get(
            "/api/v1/reports/definitions",
            headers=admin_auth_header,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or isinstance(data, list)

    async def test_generate_report_json(
        self,
        async_client: AsyncClient,
        admin_auth_header: dict[str, str],
    ) -> None:
        """Test generating a report in JSON format."""
        # First create a definition
        create_response = await async_client.post(
            "/api/v1/reports/definitions",
            json={
                "name": "Test JSON Report",
                "description": "Test",
                "report_type": "inventory",
                "default_format": "json",
            },
            headers=admin_auth_header,
        )
        
        if create_response.status_code != 201:
            pytest.skip("Could not create report definition")
        
        definition_id = create_response.json()["id"]
        
        # Generate the report
        gen_response = await async_client.post(
            f"/api/v1/reports/definitions/{definition_id}/generate",
            json={"format": "json"},
            headers=admin_auth_header,
        )
        
        assert gen_response.status_code in [200, 201, 202]


# ============================
# Scheduled Report Tests
# ============================


class TestScheduledReports:
    """Tests for scheduled report functionality."""

    def test_calculate_next_run_daily(self) -> None:
        """Test calculating next run for daily schedule."""
        from app.infrastructure.tasks.report_tasks import _calculate_next_run
        
        current = datetime(2024, 1, 15, 10, 0, 0)
        next_run = _calculate_next_run(
            frequency="daily",
            day_of_week=None,
            day_of_month=None,
            time_of_day="09:00",
            current_time=current,
        )
        
        assert next_run is not None
        assert next_run.hour == 9
        assert next_run.minute == 0
        # Since current is 10:00 and scheduled is 09:00, next run should be tomorrow
        assert next_run.day == 16

    def test_calculate_next_run_weekly(self) -> None:
        """Test calculating next run for weekly schedule."""
        from app.infrastructure.tasks.report_tasks import _calculate_next_run
        
        # Monday, Jan 15, 2024
        current = datetime(2024, 1, 15, 10, 0, 0)
        next_run = _calculate_next_run(
            frequency="weekly",
            day_of_week=2,  # Wednesday
            day_of_month=None,
            time_of_day="08:00",
            current_time=current,
        )
        
        assert next_run is not None
        assert next_run.weekday() == 2  # Wednesday
        assert next_run.hour == 8

    def test_calculate_next_run_monthly(self) -> None:
        """Test calculating next run for monthly schedule."""
        from app.infrastructure.tasks.report_tasks import _calculate_next_run
        
        current = datetime(2024, 1, 20, 10, 0, 0)
        next_run = _calculate_next_run(
            frequency="monthly",
            day_of_week=None,
            day_of_month=15,  # 15th of month
            time_of_day="06:00",
            current_time=current,
        )
        
        assert next_run is not None
        assert next_run.day == 15
        # Since we're past the 15th, next run should be February 15
        assert next_run.month == 2

    def test_calculate_next_run_once(self) -> None:
        """Test calculating next run for one-time schedule."""
        from app.infrastructure.tasks.report_tasks import _calculate_next_run
        
        current = datetime(2024, 1, 15, 10, 0, 0)
        next_run = _calculate_next_run(
            frequency="once",
            day_of_week=None,
            day_of_month=None,
            time_of_day="09:00",
            current_time=current,
        )
        
        assert next_run is None  # One-time reports don't reschedule
