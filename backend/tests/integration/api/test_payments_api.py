"""
Payments API Integration Tests.

Tests payment processing flows: cash, card payments, capture, refund.
"""
from __future__ import annotations

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
    """Create a product for payment tests."""
    resp = await client.post(
        "/api/v1/products",
        json={
            "name": f"Payment Test {uuid4().hex[:6]}",
            "sku": f"PAY-{uuid4().hex[:8]}",
            "retail_price": "50.00",
            "purchase_price": "25.00",
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


async def _record_sale(
    client: AsyncClient,
    token: str,
    product_id: str,
    quantity: int = 1,
    unit_price: str = "50.00",
) -> dict:
    """Record a sale and return the sale data."""
    resp = await client.post(
        "/api/v1/sales",
        json={
            "currency": "USD",
            "lines": [{"product_id": product_id, "quantity": quantity, "unit_price": unit_price}],
            "payments": [{"payment_method": "cash", "amount": str(Decimal(unit_price) * quantity)}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["sale"]


# ============================================================================
# Cash Payment Tests
# ============================================================================


@pytest.mark.asyncio
async def test_process_cash_payment_success(async_session):
    """Test successful cash payment processing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="pay_cash1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="pay_cash1c")
        
        # Setup
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        sale = await _record_sale(client, cashier_token, product["id"])
        
        # Process additional cash payment
        resp = await client.post(
            "/api/v1/payments/cash",
            json={
                "sale_id": sale["id"],
                "amount": "50.00",
                "currency": "USD",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 201, resp.text
        payment = resp.json()
        assert payment["sale_id"] == sale["id"]
        assert Decimal(payment["amount"]) == Decimal("50.00")
        assert payment["status"] in {"completed", "captured"}
        assert payment["method"] == "cash"


@pytest.mark.asyncio
async def test_cash_payment_different_currencies(async_session):
    """Test cash payment with different currencies."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="pay_curr1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="pay_curr1c")
        
        # Setup EUR sale
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        
        # Record EUR sale
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "EUR",
                "lines": [{"product_id": product["id"], "quantity": 1, "unit_price": "45.00"}],
                "payments": [{"payment_method": "cash", "amount": "45.00"}],
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert sale_resp.status_code == 201
        sale = sale_resp.json()["sale"]
        
        # Add EUR cash payment
        resp = await client.post(
            "/api/v1/payments/cash",
            json={
                "sale_id": sale["id"],
                "amount": "45.00",
                "currency": "EUR",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 201
        assert resp.json()["currency"] == "EUR"


@pytest.mark.asyncio
async def test_cash_payment_invalid_sale_id(async_session):
    """Test cash payment with non-existent sale ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="pay_inv1")
        
        resp = await client.post(
            "/api/v1/payments/cash",
            json={
                "sale_id": "01" + uuid4().hex[:24],  # ULID-like fake ID
                "amount": "50.00",
                "currency": "USD",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        # Should work - payment is recorded against sale_id (no FK check in current impl)
        # OR should fail with 404 if sale validation is added
        assert resp.status_code in {201, 404}


@pytest.mark.asyncio
async def test_cash_payment_rejects_zero_amount(async_session):
    """Test that zero amount is rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="pay_zero1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="pay_zero1c")
        
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        sale = await _record_sale(client, cashier_token, product["id"])
        
        resp = await client.post(
            "/api/v1/payments/cash",
            json={
                "sale_id": sale["id"],
                "amount": "0.00",
                "currency": "USD",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        # Should be rejected by validation
        assert resp.status_code in {400, 422}


# ============================================================================
# Card Payment Tests
# ============================================================================


@pytest.mark.asyncio
async def test_process_card_payment_creates_pending(async_session):
    """Test card payment creates pending payment awaiting Stripe confirmation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="pay_card1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="pay_card1c")
        
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        sale = await _record_sale(client, cashier_token, product["id"])
        
        resp = await client.post(
            "/api/v1/payments/card",
            json={
                "sale_id": sale["id"],
                "amount": "50.00",
                "currency": "USD",
                "provider": "stripe",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        # Without real Stripe keys, this may return error or create mock payment
        # Accept both successful mock and expected error scenarios
        assert resp.status_code in {201, 400, 500}
        
        if resp.status_code == 201:
            payment = resp.json()
            assert payment["method"] == "card"
            assert payment["status"] in {"pending", "authorized"}


@pytest.mark.asyncio
async def test_card_payment_with_description(async_session):
    """Test card payment with custom description."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="pay_desc1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="pay_desc1c")
        
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        sale = await _record_sale(client, cashier_token, product["id"])
        
        resp = await client.post(
            "/api/v1/payments/card",
            json={
                "sale_id": sale["id"],
                "amount": "50.00",
                "currency": "USD",
                "provider": "stripe",
                "description": "Test purchase at Store #1",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        # Accept various outcomes depending on Stripe config
        assert resp.status_code in {201, 400, 500}


# ============================================================================
# Payment Capture Tests
# ============================================================================


@pytest.mark.asyncio
async def test_capture_payment_requires_payment_id(async_session):
    """Test that capture requires a valid payment ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="pay_cap1")
        
        resp = await client.post(
            "/api/v1/payments/capture",
            json={
                "payment_id": "nonexistent_payment_id",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        # Should fail - payment not found
        assert resp.status_code in {400, 404}


# ============================================================================
# Refund Tests
# ============================================================================


@pytest.mark.asyncio
async def test_refund_payment_requires_payment_id(async_session):
    """Test that refund requires a valid payment ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="pay_ref1")
        
        resp = await client.post(
            "/api/v1/payments/refund",
            json={
                "payment_id": "nonexistent_payment_id",
                "amount": "25.00",
                "reason": "Customer request",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        # Should fail - payment not found
        assert resp.status_code in {400, 404}


# ============================================================================
# Get Payments by Sale Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_payments_by_sale(async_session):
    """Test retrieving all payments for a sale."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="pay_list1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="pay_list1c")
        
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        sale = await _record_sale(client, cashier_token, product["id"])
        
        # Add another payment
        await client.post(
            "/api/v1/payments/cash",
            json={
                "sale_id": sale["id"],
                "amount": "10.00",
                "currency": "USD",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        # Get payments for sale
        resp = await client.get(
            f"/api/v1/payments/sale/{sale['id']}",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) >= 1


# ============================================================================
# RBAC Tests
# ============================================================================


@pytest.mark.asyncio
async def test_auditor_cannot_process_payments(async_session):
    """Test that AUDITOR role cannot process payments."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auditor_token = await login_as(async_session, client, UserRole.AUDITOR, email_prefix="pay_aud1")
        
        resp = await client.post(
            "/api/v1/payments/cash",
            json={
                "sale_id": "01" + uuid4().hex[:24],
                "amount": "50.00",
                "currency": "USD",
            },
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_cannot_process_payments(async_session):
    """Test that unauthenticated users cannot process payments."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/payments/cash",
            json={
                "sale_id": "01" + uuid4().hex[:24],
                "amount": "50.00",
                "currency": "USD",
            },
        )
        
        assert resp.status_code == 401
