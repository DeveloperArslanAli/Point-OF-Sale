import datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


@pytest.mark.asyncio
async def test_vendor_performance_includes_recent_purchases(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_phase13_vendor")
        headers = {"Authorization": f"Bearer {manager_token}"}

        now = datetime.datetime.now(datetime.timezone.utc)
        suffix = now.strftime("%Y%m%d%H%M%S%f")

        supplier_resp = await client.post(
            "/api/v1/suppliers",
            json={"name": f"Vendor {suffix}", "contact_email": f"vendor{suffix}@example.com"},
            headers=headers,
        )
        assert supplier_resp.status_code == 201, supplier_resp.text
        supplier_id = supplier_resp.json()["id"]

        product_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "PO Widget",
                "sku": f"PO-{suffix}",
                "retail_price": "15.00",
                "purchase_price": "7.00",
            },
            headers=headers,
        )
        assert product_resp.status_code == 201, product_resp.text
        product_id = product_resp.json()["id"]

        purchase_resp = await client.post(
            "/api/v1/purchases",
            json={
                "supplier_id": supplier_id,
                "currency": "USD",
                "lines": [
                    {"product_id": product_id, "quantity": 10, "unit_cost": "5.00"},
                ],
            },
            headers=headers,
        )
        assert purchase_resp.status_code == 201, purchase_resp.text

        perf_resp = await client.get(
            "/api/v1/inventory/intelligence/vendors",
            params={"limit": 10},
            headers=headers,
        )
        assert perf_resp.status_code == 200, perf_resp.text
        body = perf_resp.json()
        vendors = {item["supplier_id"]: item for item in body.get("vendors", [])}

        assert supplier_id in vendors
        vendor = vendors[supplier_id]
        assert vendor["total_orders"] >= 1
        assert vendor["open_orders"] >= 0
        assert Decimal(str(vendor["total_amount"])) >= Decimal("50.00")
        assert vendor["last_order_at"] is not None
