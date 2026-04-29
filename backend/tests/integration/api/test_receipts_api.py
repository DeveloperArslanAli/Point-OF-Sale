"""
Receipts API Integration Tests.

Tests receipt generation, retrieval, PDF generation, and email sending.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


# ============================================================================
# Helper Functions
# ============================================================================


async def _create_product(client: AsyncClient, token: str) -> dict:
    """Create a product for receipt tests."""
    resp = await client.post(
        "/api/v1/products",
        json={
            "name": f"Receipt Test {uuid4().hex[:6]}",
            "sku": f"RCP-{uuid4().hex[:8]}",
            "retail_price": "29.99",
            "purchase_price": "15.00",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_stock(client: AsyncClient, token: str, product_id: str, qty: int) -> None:
    """Add inventory stock."""
    resp = await client.post(
        f"/api/v1/products/{product_id}/inventory/movements",
        json={"quantity": qty, "direction": "in", "reason": "test_stock"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text


async def _record_sale(client: AsyncClient, token: str, product: dict) -> dict:
    """Record a sale and return the sale data."""
    resp = await client.post(
        "/api/v1/sales",
        json={
            "currency": "USD",
            "lines": [{"product_id": product["id"], "quantity": 2, "unit_price": "29.99"}],
            "payments": [{"payment_method": "cash", "amount": "59.98"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["sale"]


def _build_receipt_request(sale: dict, product: dict) -> dict:
    """Build a receipt creation request payload."""
    return {
        "sale_id": sale["id"],
        "receipt_number": f"RCP-{uuid4().hex[:8].upper()}",
        "store_name": "Test Store",
        "store_address": "123 Test St, Test City, TC 12345",
        "store_phone": "+1-555-TEST",
        "cashier_name": "Test Cashier",
        "line_items": [
            {
                "product_name": product["name"],
                "sku": product["sku"],
                "quantity": 2,
                "unit_price": {"amount": "29.99", "currency": "USD"},
                "line_total": {"amount": "59.98", "currency": "USD"},
                "discount_amount": {"amount": "0.00", "currency": "USD"},
            }
        ],
        "payments": [
            {
                "payment_method": "cash",
                "amount": {"amount": "59.98", "currency": "USD"},
            }
        ],
        "totals": {
            "subtotal": {"amount": "59.98", "currency": "USD"},
            "tax_amount": {"amount": "0.00", "currency": "USD"},
            "discount_amount": {"amount": "0.00", "currency": "USD"},
            "total": {"amount": "59.98", "currency": "USD"},
            "amount_paid": {"amount": "59.98", "currency": "USD"},
            "change_given": {"amount": "0.00", "currency": "USD"},
        },
    }


# ============================================================================
# Receipt Creation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_receipt_success(async_session):
    """Test successful receipt creation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="rcp_create1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="rcp_create1c")
        
        # Setup sale
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        sale = await _record_sale(client, cashier_token, product)
        
        # Create receipt
        receipt_data = _build_receipt_request(sale, product)
        resp = await client.post(
            "/api/v1/receipts",
            json=receipt_data,
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 201, resp.text
        receipt = resp.json()
        assert receipt["sale_id"] == sale["id"]
        assert receipt["store_name"] == "Test Store"
        assert len(receipt["line_items"]) == 1
        assert len(receipt["payments"]) == 1


@pytest.mark.asyncio
async def test_create_receipt_with_multiple_items(async_session):
    """Test receipt creation with multiple line items."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="rcp_multi1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="rcp_multi1c")
        
        # Create two products
        product1 = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product1["id"], 10)
        
        product2 = await client.post(
            "/api/v1/products",
            json={
                "name": f"Product 2 {uuid4().hex[:6]}",
                "sku": f"P2-{uuid4().hex[:8]}",
                "retail_price": "15.00",
                "purchase_price": "7.50",
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        product2 = product2.json()
        await _add_stock(client, manager_token, product2["id"], 10)
        
        # Record sale with both products
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [
                    {"product_id": product1["id"], "quantity": 1, "unit_price": "29.99"},
                    {"product_id": product2["id"], "quantity": 2, "unit_price": "15.00"},
                ],
                "payments": [{"payment_method": "cash", "amount": "59.99"}],
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        sale = sale_resp.json()["sale"]
        
        # Create receipt with both items
        receipt_data = {
            "sale_id": sale["id"],
            "receipt_number": f"RCP-{uuid4().hex[:8].upper()}",
            "store_name": "Multi-Item Store",
            "store_address": "456 Multi St",
            "store_phone": "+1-555-MULTI",
            "cashier_name": "Multi Cashier",
            "line_items": [
                {
                    "product_name": product1["name"],
                    "sku": product1["sku"],
                    "quantity": 1,
                    "unit_price": {"amount": "29.99", "currency": "USD"},
                    "line_total": {"amount": "29.99", "currency": "USD"},
                    "discount_amount": {"amount": "0.00", "currency": "USD"},
                },
                {
                    "product_name": product2["name"],
                    "sku": product2["sku"],
                    "quantity": 2,
                    "unit_price": {"amount": "15.00", "currency": "USD"},
                    "line_total": {"amount": "30.00", "currency": "USD"},
                    "discount_amount": {"amount": "0.00", "currency": "USD"},
                },
            ],
            "payments": [
                {"payment_method": "cash", "amount": {"amount": "59.99", "currency": "USD"}}
            ],
            "totals": {
                "subtotal": {"amount": "59.99", "currency": "USD"},
                "tax_amount": {"amount": "0.00", "currency": "USD"},
                "discount_amount": {"amount": "0.00", "currency": "USD"},
                "total": {"amount": "59.99", "currency": "USD"},
                "amount_paid": {"amount": "59.99", "currency": "USD"},
                "change_given": {"amount": "0.00", "currency": "USD"},
            },
        }
        
        resp = await client.post(
            "/api/v1/receipts",
            json=receipt_data,
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 201, resp.text
        receipt = resp.json()
        assert len(receipt["line_items"]) == 2


@pytest.mark.asyncio
async def test_create_receipt_with_split_payments(async_session):
    """Test receipt creation with multiple payment methods."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="rcp_split1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="rcp_split1c")
        
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        
        # Sale with split payment
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [{"product_id": product["id"], "quantity": 2, "unit_price": "50.00"}],
                "payments": [
                    {"payment_method": "cash", "amount": "50.00"},
                    {"payment_method": "card", "amount": "50.00", "card_last_four": "4242"},
                ],
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        sale = sale_resp.json()["sale"]
        
        # Receipt with split payments
        receipt_data = {
            "sale_id": sale["id"],
            "receipt_number": f"RCP-{uuid4().hex[:8].upper()}",
            "store_name": "Split Payment Store",
            "store_address": "789 Split Ave",
            "store_phone": "+1-555-SPLIT",
            "cashier_name": "Split Cashier",
            "line_items": [
                {
                    "product_name": product["name"],
                    "sku": product["sku"],
                    "quantity": 2,
                    "unit_price": {"amount": "50.00", "currency": "USD"},
                    "line_total": {"amount": "100.00", "currency": "USD"},
                    "discount_amount": {"amount": "0.00", "currency": "USD"},
                }
            ],
            "payments": [
                {"payment_method": "cash", "amount": {"amount": "50.00", "currency": "USD"}},
                {
                    "payment_method": "card",
                    "amount": {"amount": "50.00", "currency": "USD"},
                    "card_last_four": "4242",
                },
            ],
            "totals": {
                "subtotal": {"amount": "100.00", "currency": "USD"},
                "tax_amount": {"amount": "0.00", "currency": "USD"},
                "discount_amount": {"amount": "0.00", "currency": "USD"},
                "total": {"amount": "100.00", "currency": "USD"},
                "amount_paid": {"amount": "100.00", "currency": "USD"},
                "change_given": {"amount": "0.00", "currency": "USD"},
            },
        }
        
        resp = await client.post(
            "/api/v1/receipts",
            json=receipt_data,
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 201, resp.text
        receipt = resp.json()
        assert len(receipt["payments"]) == 2


# ============================================================================
# Receipt Retrieval Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_receipt_by_id(async_session):
    """Test retrieving a receipt by ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="rcp_get1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="rcp_get1c")
        
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        sale = await _record_sale(client, cashier_token, product)
        
        # Create receipt
        receipt_data = _build_receipt_request(sale, product)
        create_resp = await client.post(
            "/api/v1/receipts",
            json=receipt_data,
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        created = create_resp.json()
        
        # Get by ID
        resp = await client.get(
            f"/api/v1/receipts/{created['id']}",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        receipt = resp.json()
        assert receipt["id"] == created["id"]
        assert receipt["sale_id"] == sale["id"]


@pytest.mark.asyncio
async def test_get_receipt_by_sale_id(async_session):
    """Test retrieving a receipt by sale ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="rcp_sale1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="rcp_sale1c")
        
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        sale = await _record_sale(client, cashier_token, product)
        
        # Create receipt
        receipt_data = _build_receipt_request(sale, product)
        await client.post(
            "/api/v1/receipts",
            json=receipt_data,
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        # Get by sale ID
        resp = await client.get(
            f"/api/v1/receipts/sale/{sale['id']}",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        receipt = resp.json()
        assert receipt["sale_id"] == sale["id"]


@pytest.mark.asyncio
async def test_get_receipt_not_found(async_session):
    """Test retrieving non-existent receipt."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="rcp_nf1")
        
        resp = await client.get(
            f"/api/v1/receipts/nonexistent_id",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert resp.status_code == 404


# ============================================================================
# Receipt List Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_receipts_by_date_range(async_session):
    """Test listing receipts within a date range."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="rcp_list1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="rcp_list1c")
        
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        
        # Create multiple sales and receipts
        for i in range(3):
            sale = await _record_sale(client, cashier_token, product)
            receipt_data = _build_receipt_request(sale, product)
            receipt_data["receipt_number"] = f"RCP-LIST-{i}-{uuid4().hex[:4].upper()}"
            await client.post(
                "/api/v1/receipts",
                json=receipt_data,
                headers={"Authorization": f"Bearer {cashier_token}"},
            )
        
        # List receipts
        start_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
        end_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
        
        resp = await client.get(
            f"/api/v1/receipts?start_date={start_date}&end_date={end_date}",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) >= 3


# ============================================================================
# PDF Generation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_receipt_pdf_thermal(async_session):
    """Test generating thermal receipt PDF."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="rcp_pdf1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="rcp_pdf1c")
        
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        sale = await _record_sale(client, cashier_token, product)
        
        receipt_data = _build_receipt_request(sale, product)
        create_resp = await client.post(
            "/api/v1/receipts",
            json=receipt_data,
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        receipt = create_resp.json()
        
        # Get thermal PDF
        resp = await client.get(
            f"/api/v1/receipts/{receipt['id']}/pdf?format=thermal",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("content-type") == "application/pdf"


@pytest.mark.asyncio
async def test_get_receipt_pdf_a4(async_session):
    """Test generating A4 receipt PDF."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="rcp_a4_1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="rcp_a4_1c")
        
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        sale = await _record_sale(client, cashier_token, product)
        
        receipt_data = _build_receipt_request(sale, product)
        create_resp = await client.post(
            "/api/v1/receipts",
            json=receipt_data,
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        receipt = create_resp.json()
        
        # Get A4 PDF
        resp = await client.get(
            f"/api/v1/receipts/{receipt['id']}/pdf?format=a4",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("content-type") == "application/pdf"


# ============================================================================
# Email Receipt Tests
# ============================================================================


@pytest.mark.asyncio
async def test_email_receipt_queues_task(async_session):
    """Test that emailing a receipt queues a Celery task."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="rcp_email1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="rcp_email1c")
        
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        sale = await _record_sale(client, cashier_token, product)
        
        receipt_data = _build_receipt_request(sale, product)
        create_resp = await client.post(
            "/api/v1/receipts",
            json=receipt_data,
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        receipt = create_resp.json()
        
        # Email receipt
        resp = await client.post(
            f"/api/v1/receipts/{receipt['id']}/email",
            json={"email": "customer@example.com"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        # Should accept and queue (or return success/202)
        assert resp.status_code in {200, 202}, resp.text


# ============================================================================
# RBAC Tests
# ============================================================================


@pytest.mark.asyncio
async def test_auditor_cannot_create_receipt(async_session):
    """Test that AUDITOR role cannot create receipts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auditor_token = await login_as(async_session, client, UserRole.AUDITOR, email_prefix="rcp_aud1")
        
        resp = await client.post(
            "/api/v1/receipts",
            json={
                "sale_id": "test_sale",
                "receipt_number": "RCP-TEST",
                "store_name": "Test",
                "store_address": "Test",
                "store_phone": "Test",
                "cashier_name": "Test",
                "line_items": [],
                "payments": [],
                "totals": {
                    "subtotal": {"amount": "0.00", "currency": "USD"},
                    "tax_amount": {"amount": "0.00", "currency": "USD"},
                    "discount_amount": {"amount": "0.00", "currency": "USD"},
                    "total": {"amount": "0.00", "currency": "USD"},
                    "amount_paid": {"amount": "0.00", "currency": "USD"},
                    "change_given": {"amount": "0.00", "currency": "USD"},
                },
            },
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_receipts(async_session):
    """Test that unauthenticated users cannot access receipts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/receipts")
        
        assert resp.status_code == 401
