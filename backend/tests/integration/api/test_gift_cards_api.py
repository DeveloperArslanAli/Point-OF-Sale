"""
Gift Card API Integration Tests.

Tests the complete gift card lifecycle: purchase, activate, redeem, balance check,
and integration with sales flow.
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


async def _create_customer(client: AsyncClient, token: str) -> dict:
    """Create a customer for gift card assignment."""
    resp = await client.post(
        "/api/v1/customers",
        json={
            "first_name": "Gift",
            "last_name": "Recipient",
            "email": f"gc_{uuid4().hex[:8]}@example.com",
            "phone": "+15550000001",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _purchase_gift_card(
    client: AsyncClient,
    token: str,
    *,
    amount: str = "50.00",
    currency: str = "USD",
    customer_id: str | None = None,
    validity_days: int | None = None,
) -> dict:
    """Purchase a new gift card."""
    payload: dict = {
        "amount": amount,
        "currency": currency,
    }
    if customer_id:
        payload["customer_id"] = customer_id
    if validity_days:
        payload["validity_days"] = validity_days
        
    resp = await client.post(
        "/api/v1/gift-cards/purchase",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


async def _activate_gift_card(client: AsyncClient, token: str, code: str) -> dict:
    """Activate a gift card by code."""
    resp = await client.post(
        "/api/v1/gift-cards/activate",
        json={"code": code},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


async def _redeem_gift_card(
    client: AsyncClient, token: str, code: str, amount: str, currency: str = "USD"
) -> dict:
    """Redeem value from a gift card."""
    resp = await client.post(
        "/api/v1/gift-cards/redeem",
        json={
            "code": code,
            "amount": amount,
            "currency": currency,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


async def _check_balance(client: AsyncClient, token: str, code: str) -> dict:
    """Check gift card balance."""
    resp = await client.get(
        f"/api/v1/gift-cards/{code}/balance",
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


async def _list_customer_cards(client: AsyncClient, token: str, customer_id: str) -> dict:
    """List gift cards for a customer."""
    resp = await client.get(
        f"/api/v1/gift-cards/customer/{customer_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


# ============================================================================
# Gift Card Purchase Tests
# ============================================================================


@pytest.mark.asyncio
async def test_purchase_gift_card_success(async_session):
    """Test successful gift card purchase."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_cashier1")
        
        resp = await _purchase_gift_card(client, token, amount="100.00")
        
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "pending"
        assert Decimal(data["initial_balance"]) == Decimal("100.00")
        assert Decimal(data["current_balance"]) == Decimal("100.00")
        assert data["currency"] == "USD"
        assert data["code"].startswith("GC-")
        assert len(data["code"]) == 15  # GC- + 12 chars


@pytest.mark.asyncio
async def test_purchase_gift_card_with_customer(async_session):
    """Test purchasing a gift card for a specific customer."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="gc_mgr1")
        
        customer = await _create_customer(client, manager_token)
        resp = await _purchase_gift_card(
            client, manager_token,
            amount="75.00",
            customer_id=customer["id"],
        )
        
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["customer_id"] == customer["id"]


@pytest.mark.asyncio
async def test_purchase_gift_card_with_custom_validity(async_session):
    """Test purchasing a gift card with custom validity period."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_cashier2")
        
        resp = await _purchase_gift_card(client, token, amount="50.00", validity_days=730)
        
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["expiry_date"] is not None


@pytest.mark.asyncio
async def test_purchase_gift_card_invalid_amount(async_session):
    """Test that negative amounts are rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_cashier3")
        
        resp = await client.post(
            "/api/v1/gift-cards/purchase",
            json={"amount": "-10.00", "currency": "USD"},
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert resp.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_purchase_gift_card_unauthorized(async_session):
    """Test that unauthenticated requests are rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/gift-cards/purchase",
            json={"amount": "50.00", "currency": "USD"},
        )
        
        assert resp.status_code == 401


# ============================================================================
# Gift Card Activation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_activate_gift_card_success(async_session):
    """Test successful gift card activation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_act1")
        
        # Purchase
        purchase_resp = await _purchase_gift_card(client, token)
        assert purchase_resp.status_code == 201
        card = purchase_resp.json()
        assert card["status"] == "pending"
        
        # Activate
        activate_resp = await _activate_gift_card(client, token, card["code"])
        
        assert activate_resp.status_code == 200, activate_resp.text
        activated = activate_resp.json()
        assert activated["status"] == "active"
        assert activated["code"] == card["code"]


@pytest.mark.asyncio
async def test_activate_gift_card_not_found(async_session):
    """Test activation of non-existent gift card."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_act2")
        
        resp = await _activate_gift_card(client, token, "GC-NONEXISTENT1")
        
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_activate_already_active_card(async_session):
    """Test that activating an already active card fails."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_act3")
        
        # Purchase and activate
        purchase_resp = await _purchase_gift_card(client, token)
        card = purchase_resp.json()
        await _activate_gift_card(client, token, card["code"])
        
        # Try to activate again
        resp = await _activate_gift_card(client, token, card["code"])
        
        assert resp.status_code == 400


# ============================================================================
# Gift Card Redemption Tests
# ============================================================================


@pytest.mark.asyncio
async def test_redeem_gift_card_partial(async_session):
    """Test partial redemption of gift card."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_red1")
        
        # Purchase and activate $100 card
        purchase_resp = await _purchase_gift_card(client, token, amount="100.00")
        card = purchase_resp.json()
        await _activate_gift_card(client, token, card["code"])
        
        # Redeem $30
        redeem_resp = await _redeem_gift_card(client, token, card["code"], "30.00")
        
        assert redeem_resp.status_code == 200, redeem_resp.text
        redeemed = redeem_resp.json()
        assert Decimal(redeemed["current_balance"]) == Decimal("70.00")
        assert redeemed["status"] == "active"  # Still has balance


@pytest.mark.asyncio
async def test_redeem_gift_card_full(async_session):
    """Test full redemption of gift card."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_red2")
        
        # Purchase and activate $50 card
        purchase_resp = await _purchase_gift_card(client, token, amount="50.00")
        card = purchase_resp.json()
        await _activate_gift_card(client, token, card["code"])
        
        # Redeem full amount
        redeem_resp = await _redeem_gift_card(client, token, card["code"], "50.00")
        
        assert redeem_resp.status_code == 200, redeem_resp.text
        redeemed = redeem_resp.json()
        assert Decimal(redeemed["current_balance"]) == Decimal("0.00")
        assert redeemed["status"] == "redeemed"


@pytest.mark.asyncio
async def test_redeem_gift_card_exceeds_balance(async_session):
    """Test that redeeming more than balance fails."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_red3")
        
        # Purchase and activate $25 card
        purchase_resp = await _purchase_gift_card(client, token, amount="25.00")
        card = purchase_resp.json()
        await _activate_gift_card(client, token, card["code"])
        
        # Try to redeem $30
        redeem_resp = await _redeem_gift_card(client, token, card["code"], "30.00")
        
        assert redeem_resp.status_code == 400


@pytest.mark.asyncio
async def test_redeem_inactive_gift_card(async_session):
    """Test that redeeming an inactive card fails."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_red4")
        
        # Purchase but don't activate
        purchase_resp = await _purchase_gift_card(client, token, amount="50.00")
        card = purchase_resp.json()
        
        # Try to redeem
        redeem_resp = await _redeem_gift_card(client, token, card["code"], "25.00")
        
        assert redeem_resp.status_code == 400


# ============================================================================
# Gift Card Balance Check Tests
# ============================================================================


@pytest.mark.asyncio
async def test_check_balance_success(async_session):
    """Test checking gift card balance."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_bal1")
        
        # Purchase and activate
        purchase_resp = await _purchase_gift_card(client, token, amount="80.00")
        card = purchase_resp.json()
        await _activate_gift_card(client, token, card["code"])
        
        # Check balance
        balance_resp = await _check_balance(client, token, card["code"])
        
        assert balance_resp.status_code == 200, balance_resp.text
        data = balance_resp.json()
        assert Decimal(data["balance"]) == Decimal("80.00")
        assert data["currency"] == "USD"
        assert data["status"] == "active"


@pytest.mark.asyncio
async def test_check_balance_not_found(async_session):
    """Test checking balance of non-existent card."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_bal2")
        
        resp = await _check_balance(client, token, "GC-NONEXISTENT2")
        
        assert resp.status_code == 404


# ============================================================================
# Customer Gift Cards List Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_customer_gift_cards(async_session):
    """Test listing gift cards for a customer."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="gc_list1")
        
        # Create customer
        customer = await _create_customer(client, manager_token)
        
        # Purchase multiple cards for customer
        await _purchase_gift_card(client, manager_token, amount="50.00", customer_id=customer["id"])
        await _purchase_gift_card(client, manager_token, amount="100.00", customer_id=customer["id"])
        
        # List cards
        resp = await _list_customer_cards(client, manager_token, customer["id"])
        
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_customer_gift_cards_empty(async_session):
    """Test listing cards for customer with no cards."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="gc_list2")
        
        # Create customer
        customer = await _create_customer(client, manager_token)
        
        # List cards
        resp = await _list_customer_cards(client, manager_token, customer["id"])
        
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 0


# ============================================================================
# Gift Card + Sales Integration Tests
# ============================================================================


async def _create_product(client: AsyncClient, token: str) -> dict:
    """Create a product for sale tests."""
    resp = await client.post(
        "/api/v1/products",
        json={
            "name": f"GC Test Product {uuid4().hex[:6]}",
            "sku": f"GC-SKU-{uuid4().hex[:8]}",
            "retail_price": "25.00",
            "purchase_price": "10.00",
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


@pytest.mark.asyncio
async def test_sale_with_gift_card_payment(async_session):
    """Test recording a sale with gift card as payment method."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="gc_sale1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_sale1c")
        
        # Setup: Create product with stock
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        
        # Setup: Purchase and activate gift card
        gc_resp = await _purchase_gift_card(client, cashier_token, amount="100.00")
        gc = gc_resp.json()
        await _activate_gift_card(client, cashier_token, gc["code"])
        
        # Record sale with gift card payment ($50 total)
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [{"product_id": product["id"], "quantity": 2, "unit_price": "25.00"}],
                "payments": [
                    {
                        "payment_method": "gift_card",
                        "amount": "50.00",
                        "gift_card_code": gc["code"],
                    }
                ],
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert sale_resp.status_code == 201, sale_resp.text
        sale = sale_resp.json()["sale"]
        assert Decimal(sale["total_amount"]) == Decimal("50.00")
        
        # Verify gift card balance reduced
        balance_resp = await _check_balance(client, cashier_token, gc["code"])
        balance = balance_resp.json()
        assert Decimal(balance["balance"]) == Decimal("50.00")  # 100 - 50


@pytest.mark.asyncio
async def test_sale_with_split_payment_gift_card_and_cash(async_session):
    """Test recording a sale with split payment: gift card + cash."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="gc_split1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_split1c")
        
        # Setup: Product with stock
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        
        # Setup: $30 gift card
        gc_resp = await _purchase_gift_card(client, cashier_token, amount="30.00")
        gc = gc_resp.json()
        await _activate_gift_card(client, cashier_token, gc["code"])
        
        # Record $50 sale with $30 gift card + $20 cash
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [{"product_id": product["id"], "quantity": 2, "unit_price": "25.00"}],
                "payments": [
                    {
                        "payment_method": "gift_card",
                        "amount": "30.00",
                        "gift_card_code": gc["code"],
                    },
                    {
                        "payment_method": "cash",
                        "amount": "20.00",
                    },
                ],
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert sale_resp.status_code == 201, sale_resp.text
        sale = sale_resp.json()["sale"]
        assert len(sale["payments"]) == 2
        
        # Gift card should be fully redeemed
        balance_resp = await _check_balance(client, cashier_token, gc["code"])
        balance = balance_resp.json()
        assert Decimal(balance["balance"]) == Decimal("0.00")
        assert balance["status"] == "redeemed"


@pytest.mark.asyncio
async def test_sale_with_insufficient_gift_card_balance(async_session):
    """Test sale fails when gift card has insufficient balance."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="gc_insuf1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_insuf1c")
        
        # Setup: Product with stock
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        
        # Setup: $20 gift card
        gc_resp = await _purchase_gift_card(client, cashier_token, amount="20.00")
        gc = gc_resp.json()
        await _activate_gift_card(client, cashier_token, gc["code"])
        
        # Try $50 sale with only $20 gift card (should fail)
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [{"product_id": product["id"], "quantity": 2, "unit_price": "25.00"}],
                "payments": [
                    {
                        "payment_method": "gift_card",
                        "amount": "50.00",
                        "gift_card_code": gc["code"],
                    }
                ],
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert sale_resp.status_code == 400


@pytest.mark.asyncio
async def test_sale_with_inactive_gift_card(async_session):
    """Test sale fails when gift card is not activated."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="gc_inact1")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="gc_inact1c")
        
        # Setup: Product with stock
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], 10)
        
        # Setup: Unactivated gift card
        gc_resp = await _purchase_gift_card(client, cashier_token, amount="100.00")
        gc = gc_resp.json()
        # NOT activating
        
        # Try sale with inactive card
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [{"product_id": product["id"], "quantity": 1, "unit_price": "25.00"}],
                "payments": [
                    {
                        "payment_method": "gift_card",
                        "amount": "25.00",
                        "gift_card_code": gc["code"],
                    }
                ],
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert sale_resp.status_code == 400


# ============================================================================
# RBAC Tests
# ============================================================================


@pytest.mark.asyncio
async def test_auditor_cannot_purchase_gift_card(async_session):
    """Test that AUDITOR role cannot purchase gift cards (SALES_ROLES required)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auditor_token = await login_as(async_session, client, UserRole.AUDITOR, email_prefix="gc_aud1")
        
        resp = await _purchase_gift_card(client, auditor_token)
        
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_manage_gift_cards(async_session):
    """Test that ADMIN role can manage gift cards."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="gc_admin1")
        
        # Purchase
        resp = await _purchase_gift_card(client, admin_token, amount="200.00")
        assert resp.status_code == 201
        
        # Activate
        card = resp.json()
        resp = await _activate_gift_card(client, admin_token, card["code"])
        assert resp.status_code == 200
        
        # Redeem
        resp = await _redeem_gift_card(client, admin_token, card["code"], "50.00")
        assert resp.status_code == 200
