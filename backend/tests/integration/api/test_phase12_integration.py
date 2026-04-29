import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


# Payments: happy path cash and negative amount rejection
@pytest.mark.asyncio
async def test_cash_payment_happy_path(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_cashpay")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="cashier")

        # Create product and seed stock so sale can be recorded
        product_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "CashSaleWidget",
                "sku": f"CS-{uuid.uuid4().hex[:6]}",
                "retail_price": "12.34",
                "purchase_price": "6.00",
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert product_resp.status_code == 201, product_resp.text
        product_id = product_resp.json()["id"]

        stock_resp = await client.post(
            f"/api/v1/products/{product_id}/inventory/movements",
            json={"quantity": 5, "direction": "in", "reason": "init"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert stock_resp.status_code == 201, stock_resp.text

        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [{"product_id": product_id, "quantity": 1, "unit_price": "12.34"}],
                "payments": [{"payment_method": "cash", "amount": "12.34"}],
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert sale_resp.status_code == 201, sale_resp.text
        sale_id = sale_resp.json()["sale"]["id"]

        # Record an additional cash payment against the sale
        resp = await client.post(
            "/api/v1/payments/cash",
            json={"sale_id": sale_id, "amount": "12.34", "currency": "USD"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["sale_id"] == sale_id
        assert Decimal(body["amount"]) == Decimal("12.34")
        assert body["status"] in {"completed", "captured"}


@pytest.mark.asyncio
async def test_cash_payment_rejects_negative(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="cashier_neg")

        resp = await client.post(
            "/api/v1/payments/cash",
            json={"sale_id": "01" + uuid.uuid4().hex[:24], "amount": "-1", "currency": "USD"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Pydantic validation hits first: expect 422
        assert resp.status_code == 422


# Promotions: apply and role 403 on create
@pytest.mark.asyncio
async def test_apply_promotion_coupon_flow(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="admin_promo")
        coupon_code = f"TEN{uuid.uuid4().hex[:6].upper()}"

        # Create a simple percentage promotion
        promo_resp = await client.post(
            "/api/v1/promotions",
            json={
                "name": "TenOff",
                "description": "10 percent off",
                "discount_type": "percentage",
                "value": 10,
                "priority": 1,
                "coupon_code": coupon_code,
                "start_date": "2025-01-01T00:00:00Z",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert promo_resp.status_code == 201, promo_resp.text
        promo_id = promo_resp.json()["id"]

        activate_resp = await client.post(
            f"/api/v1/promotions/{promo_id}/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert activate_resp.status_code == 200, activate_resp.text

        apply_resp = await client.post(
            "/api/v1/promotions/apply",
            json={
                "promotion_id": promo_id,
                "subtotal": "100.00",
                "currency": "USD",
                "quantity": 1,
                "coupon_code": coupon_code,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert apply_resp.status_code == 200, apply_resp.text
        data = apply_resp.json()
        assert Decimal(data["discount_amount"]) == Decimal("10.00")


@pytest.mark.asyncio
async def test_cashier_cannot_create_promotion(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="cashier_promo")

        resp = await client.post(
            "/api/v1/promotions",
            json={
                "name": "Nope",
                "description": "Denied",
                "discount_type": "percentage",
                "value": 5,
                "start_date": "2025-01-01T00:00:00Z",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert resp.status_code == 403
        assert resp.json().get("code") == "insufficient_role"


# Receipts: 404 for missing ID
@pytest.mark.asyncio
async def test_receipt_fetch_not_found(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_receipt")

        resp = await client.get(
            f"/api/v1/receipts/{uuid.uuid4().hex}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


# Split payments: create sale with multiple payments and verify echo
@pytest.mark.asyncio
async def test_sale_with_split_payments(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_split")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="cashier_split")

        # Create a product (manager)
        product_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "SplitWidget",
                "sku": f"SW-{uuid.uuid4().hex[:6]}",
                "retail_price": "20.00",
                "purchase_price": "10.00",
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert product_resp.status_code == 201, product_resp.text
        product_id = product_resp.json()["id"]

        # Add stock (manager)
        stock_resp = await client.post(
            f"/api/v1/products/{product_id}/inventory/movements",
            json={"quantity": 2, "direction": "in", "reason": "initial_stock"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert stock_resp.status_code == 201, stock_resp.text

        # Create sale with split payments (cashier)
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [
                    {"product_id": product_id, "quantity": 1, "unit_price": "20.00"}
                ],
                "payments": [
                    {"payment_method": "cash", "amount": "5.00"},
                    {"payment_method": "card", "amount": "15.00"},
                ],
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert sale_resp.status_code == 201, sale_resp.text
        sale_body = sale_resp.json()
        payments = sale_body["sale"]["payments"]
        assert len(payments) == 2
        amounts = sorted(Decimal(p["amount"]) for p in payments)
        assert amounts == [Decimal("5.00"), Decimal("15.00")]


# Gift cards: purchase -> activate -> redeem; RBAC enforced
@pytest.mark.asyncio
async def test_gift_card_flow_and_rbac(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="cashier_gc")
        auditor_token = await login_as(async_session, client, UserRole.AUDITOR, email_prefix="aud_gc")

        # Auditor blocked on purchase
        bad_resp = await client.post(
            "/api/v1/gift-cards/purchase",
            json={"amount": "25.00", "currency": "USD", "validity_days": 365},
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert bad_resp.status_code == 403

        # Cashier purchases
        purchase = await client.post(
            "/api/v1/gift-cards/purchase",
            json={"amount": "25.00", "currency": "USD", "validity_days": 365},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert purchase.status_code == 201, purchase.text
        code = purchase.json()["code"]

        # Activate
        activate = await client.post(
            "/api/v1/gift-cards/activate",
            json={"code": code},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert activate.status_code == 200, activate.text
        assert activate.json()["status"].lower() == "active"

        # Redeem partial amount
        redeem = await client.post(
            "/api/v1/gift-cards/redeem",
            json={"code": code, "amount": "5.00", "currency": "USD"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert redeem.status_code == 200, redeem.text
        assert Decimal(redeem.json()["current_balance"]) == Decimal("20.00")
