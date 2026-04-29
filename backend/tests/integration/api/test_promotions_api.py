"""
Promotions API Integration Tests.

Tests promotion creation, application, validation, and RBAC.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def _future_date(days: int = 30) -> str:
    """Return ISO format date N days from now."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _past_date(days: int = 30) -> str:
    """Return ISO format date N days ago."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


async def _create_promotion(
    client: AsyncClient,
    token: str,
    *,
    name: str = "Test Promo",
    discount_type: str = "percentage",
    value: float = 10.0,
    coupon_code: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    min_purchase: float | None = None,
    max_discount: float | None = None,
) -> dict:
    """Create a promotion and return the response."""
    payload = {
        "name": name,
        "description": f"Test promotion: {name}",
        "discount_type": discount_type,
        "value": value,
        "start_date": start_date or _past_date(1),
        "priority": 1,
    }
    if coupon_code:
        payload["coupon_code"] = coupon_code
    if end_date:
        payload["end_date"] = end_date
    if min_purchase is not None:
        payload["min_purchase_amount"] = min_purchase
    if max_discount is not None:
        payload["max_discount_amount"] = max_discount
        
    resp = await client.post(
        "/api/v1/promotions",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


async def _activate_promotion(client: AsyncClient, token: str, promo_id: str) -> dict:
    """Activate a promotion."""
    resp = await client.post(
        f"/api/v1/promotions/{promo_id}/activate",
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


# ============================================================================
# Promotion Creation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_percentage_promotion(async_session):
    """Test creating a percentage discount promotion."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_pct1")
        
        resp = await _create_promotion(
            client, admin_token,
            name="10% Off Everything",
            discount_type="percentage",
            value=10.0,
        )
        
        assert resp.status_code == 201, resp.text
        promo = resp.json()
        assert promo["name"] == "10% Off Everything"
        assert promo["discount_rule"]["discount_type"] == "percentage"
        assert promo["discount_rule"]["value"] == 10.0
        assert promo["status"] == "draft"


@pytest.mark.asyncio
async def test_create_fixed_amount_promotion(async_session):
    """Test creating a fixed amount discount promotion."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_fix1")
        
        resp = await _create_promotion(
            client, admin_token,
            name="$5 Off",
            discount_type="fixed_amount",
            value=5.0,
        )
        
        assert resp.status_code == 201, resp.text
        promo = resp.json()
        assert promo["discount_rule"]["discount_type"] == "fixed_amount"
        assert promo["discount_rule"]["value"] == 5.0


@pytest.mark.asyncio
async def test_create_promotion_with_coupon_code(async_session):
    """Test creating a promotion with coupon code."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_coup1")
        
        coupon = f"SAVE20-{uuid4().hex[:6].upper()}"
        resp = await _create_promotion(
            client, admin_token,
            name="20% with Coupon",
            discount_type="percentage",
            value=20.0,
            coupon_code=coupon,
        )
        
        assert resp.status_code == 201, resp.text
        promo = resp.json()
        assert promo["coupon_code"] == coupon


@pytest.mark.asyncio
async def test_create_promotion_with_min_purchase(async_session):
    """Test creating a promotion with minimum purchase requirement."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_min1")
        
        resp = await _create_promotion(
            client, admin_token,
            name="$10 Off $50+",
            discount_type="fixed_amount",
            value=10.0,
            min_purchase=50.0,
        )
        
        assert resp.status_code == 201, resp.text
        promo = resp.json()
        assert promo["discount_rule"]["min_purchase_amount"] == 50.0


@pytest.mark.asyncio
async def test_create_promotion_with_max_discount(async_session):
    """Test creating a promotion with maximum discount cap."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_max1")
        
        resp = await _create_promotion(
            client, admin_token,
            name="25% Off (Max $20)",
            discount_type="percentage",
            value=25.0,
            max_discount=20.0,
        )
        
        assert resp.status_code == 201, resp.text
        promo = resp.json()
        assert promo["discount_rule"]["max_discount_amount"] == 20.0


# ============================================================================
# Promotion Activation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_activate_promotion(async_session):
    """Test activating a draft promotion."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_act1")
        
        # Create draft
        create_resp = await _create_promotion(client, admin_token, name="To Activate")
        promo = create_resp.json()
        assert promo["status"] == "draft"
        
        # Activate
        activate_resp = await _activate_promotion(client, admin_token, promo["id"])
        
        assert activate_resp.status_code == 200, activate_resp.text
        activated = activate_resp.json()
        assert activated["status"] == "active"


@pytest.mark.asyncio
async def test_deactivate_promotion(async_session):
    """Test deactivating an active promotion."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_deact1")
        
        # Create and activate
        create_resp = await _create_promotion(client, admin_token, name="To Deactivate")
        promo = create_resp.json()
        await _activate_promotion(client, admin_token, promo["id"])
        
        # Deactivate
        resp = await client.post(
            f"/api/v1/promotions/{promo['id']}/deactivate",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        deactivated = resp.json()
        assert deactivated["status"] == "inactive"


# ============================================================================
# Promotion Application Tests
# ============================================================================


@pytest.mark.asyncio
async def test_apply_percentage_promotion(async_session):
    """Test applying a percentage discount."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_apply1")
        
        # Create and activate 15% off
        create_resp = await _create_promotion(
            client, admin_token,
            name="15% Off",
            discount_type="percentage",
            value=15.0,
        )
        promo = create_resp.json()
        await _activate_promotion(client, admin_token, promo["id"])
        
        # Apply to $100 subtotal
        resp = await client.post(
            "/api/v1/promotions/apply",
            json={
                "promotion_id": promo["id"],
                "subtotal": "100.00",
                "currency": "USD",
                "quantity": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert Decimal(result["discount_amount"]) == Decimal("15.00")


@pytest.mark.asyncio
async def test_apply_fixed_amount_promotion(async_session):
    """Test applying a fixed amount discount."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_apply2")
        
        # Create and activate $10 off
        create_resp = await _create_promotion(
            client, admin_token,
            name="$10 Off",
            discount_type="fixed_amount",
            value=10.0,
        )
        promo = create_resp.json()
        await _activate_promotion(client, admin_token, promo["id"])
        
        # Apply to $50 subtotal
        resp = await client.post(
            "/api/v1/promotions/apply",
            json={
                "promotion_id": promo["id"],
                "subtotal": "50.00",
                "currency": "USD",
                "quantity": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert Decimal(result["discount_amount"]) == Decimal("10.00")


@pytest.mark.asyncio
async def test_apply_promotion_with_coupon_code(async_session):
    """Test applying a promotion using coupon code."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_coup2")
        
        coupon = f"DISCOUNT-{uuid4().hex[:6].upper()}"
        create_resp = await _create_promotion(
            client, admin_token,
            name="Coupon Discount",
            discount_type="percentage",
            value=20.0,
            coupon_code=coupon,
        )
        promo = create_resp.json()
        await _activate_promotion(client, admin_token, promo["id"])
        
        # Apply with coupon
        resp = await client.post(
            "/api/v1/promotions/apply",
            json={
                "promotion_id": promo["id"],
                "subtotal": "80.00",
                "currency": "USD",
                "quantity": 1,
                "coupon_code": coupon,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert Decimal(result["discount_amount"]) == Decimal("16.00")


@pytest.mark.asyncio
async def test_apply_promotion_respects_max_discount(async_session):
    """Test that max discount cap is enforced."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_maxd1")
        
        # 50% off but max $25 discount
        create_resp = await _create_promotion(
            client, admin_token,
            name="50% Off (Max $25)",
            discount_type="percentage",
            value=50.0,
            max_discount=25.0,
        )
        promo = create_resp.json()
        await _activate_promotion(client, admin_token, promo["id"])
        
        # Apply to $100 (50% would be $50, but capped at $25)
        resp = await client.post(
            "/api/v1/promotions/apply",
            json={
                "promotion_id": promo["id"],
                "subtotal": "100.00",
                "currency": "USD",
                "quantity": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert Decimal(result["discount_amount"]) == Decimal("25.00")


@pytest.mark.asyncio
async def test_apply_promotion_fails_below_min_purchase(async_session):
    """Test that promotion fails when below minimum purchase."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_minf1")
        
        # $10 off with $50 minimum
        create_resp = await _create_promotion(
            client, admin_token,
            name="$10 Off $50+",
            discount_type="fixed_amount",
            value=10.0,
            min_purchase=50.0,
        )
        promo = create_resp.json()
        await _activate_promotion(client, admin_token, promo["id"])
        
        # Apply to $30 (below minimum)
        resp = await client.post(
            "/api/v1/promotions/apply",
            json={
                "promotion_id": promo["id"],
                "subtotal": "30.00",
                "currency": "USD",
                "quantity": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        # Should fail or return 0 discount
        if resp.status_code == 200:
            result = resp.json()
            assert Decimal(result["discount_amount"]) == Decimal("0.00")
        else:
            assert resp.status_code == 400


# ============================================================================
# Coupon Validation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_validate_coupon_success(async_session):
    """Test validating a valid coupon code."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_val1")
        
        coupon = f"VALID-{uuid4().hex[:6].upper()}"
        create_resp = await _create_promotion(
            client, admin_token,
            name="Valid Coupon Promo",
            discount_type="percentage",
            value=10.0,
            coupon_code=coupon,
        )
        promo = create_resp.json()
        await _activate_promotion(client, admin_token, promo["id"])
        
        # Validate coupon
        resp = await client.post(
            "/api/v1/promotions/validate-coupon",
            json={"coupon_code": coupon},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["valid"] is True
        assert result["promotion_id"] == promo["id"]


@pytest.mark.asyncio
async def test_validate_coupon_invalid(async_session):
    """Test validating an invalid coupon code."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_inv1")
        
        resp = await client.post(
            "/api/v1/promotions/validate-coupon",
            json={"coupon_code": "INVALID-NONEXISTENT"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        # Should return invalid or 404
        if resp.status_code == 200:
            result = resp.json()
            assert result["valid"] is False
        else:
            assert resp.status_code == 404


# ============================================================================
# Promotion Listing Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_active_promotions(async_session):
    """Test listing active promotions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_list1")
        
        # Create and activate multiple promotions
        for i in range(3):
            create_resp = await _create_promotion(
                client, admin_token,
                name=f"List Promo {i}",
                discount_type="percentage",
                value=5.0 * (i + 1),
            )
            promo = create_resp.json()
            await _activate_promotion(client, admin_token, promo["id"])
        
        # List active promotions
        resp = await client.get(
            "/api/v1/promotions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) >= 3


@pytest.mark.asyncio
async def test_get_promotion_by_id(async_session):
    """Test getting a specific promotion by ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_get1")
        
        create_resp = await _create_promotion(client, admin_token, name="Get By ID Test")
        promo = create_resp.json()
        
        resp = await client.get(
            f"/api/v1/promotions/{promo['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        fetched = resp.json()
        assert fetched["id"] == promo["id"]
        assert fetched["name"] == "Get By ID Test"


# ============================================================================
# Promotion Update Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_promotion(async_session):
    """Test updating a promotion."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_upd1")
        
        create_resp = await _create_promotion(
            client, admin_token,
            name="Original Name",
            discount_type="percentage",
            value=10.0,
        )
        promo = create_resp.json()
        
        # Update
        resp = await client.put(
            f"/api/v1/promotions/{promo['id']}",
            json={
                "name": "Updated Name",
                "description": "Updated description",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        assert resp.status_code == 200, resp.text
        updated = resp.json()
        assert updated["name"] == "Updated Name"


# ============================================================================
# Promotion Delete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_delete_promotion(async_session):
    """Test deleting a promotion."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_del1")
        
        create_resp = await _create_promotion(client, admin_token, name="To Delete")
        promo = create_resp.json()
        
        # Delete
        resp = await client.delete(
            f"/api/v1/promotions/{promo['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        assert resp.status_code in {200, 204}, resp.text
        
        # Verify deleted
        get_resp = await client.get(
            f"/api/v1/promotions/{promo['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_resp.status_code == 404


# ============================================================================
# RBAC Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cashier_cannot_create_promotion(async_session):
    """Test that CASHIER role cannot create promotions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="promo_rbac1")
        
        resp = await _create_promotion(client, cashier_token, name="Unauthorized")
        
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cashier_can_apply_promotion(async_session):
    """Test that CASHIER role can apply promotions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="promo_rbac2a")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="promo_rbac2c")
        
        # Admin creates and activates
        create_resp = await _create_promotion(
            client, admin_token,
            name="Cashier Apply Test",
            discount_type="percentage",
            value=10.0,
        )
        promo = create_resp.json()
        await _activate_promotion(client, admin_token, promo["id"])
        
        # Cashier applies
        resp = await client.post(
            "/api/v1/promotions/apply",
            json={
                "promotion_id": promo["id"],
                "subtotal": "100.00",
                "currency": "USD",
                "quantity": 1,
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_manager_can_create_promotion(async_session):
    """Test that MANAGER role can create promotions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="promo_mgr1")
        
        resp = await _create_promotion(client, manager_token, name="Manager Promo")
        
        assert resp.status_code == 201, resp.text
