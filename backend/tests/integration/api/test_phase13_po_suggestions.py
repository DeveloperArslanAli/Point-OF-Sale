import datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


@pytest.mark.asyncio
async def test_po_suggestions_recommend_order(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_phase13_po")
        headers = {"Authorization": f"Bearer {manager_token}"}

        now = datetime.datetime.now(datetime.timezone.utc)
        suffix = now.strftime("%Y%m%d%H%M%S%f")

        prod_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "SuggestWidget",
                "sku": f"SG-{suffix}",
                "retail_price": "20.00",
                "purchase_price": "8.00",
            },
            headers=headers,
        )
        assert prod_resp.status_code == 201, prod_resp.text
        product_id = prod_resp.json()["id"]

        in_resp = await client.post(
            f"/api/v1/inventory/products/{product_id}/movements",
            json={
                "quantity": 50,
                "direction": "in",
                "reason": "initial",
                "occurred_at": (now - datetime.timedelta(days=3)).isoformat(),
            },
            headers=headers,
        )
        assert in_resp.status_code == 201, in_resp.text

        out_resp = await client.post(
            f"/api/v1/inventory/products/{product_id}/movements",
            json={
                "quantity": 40,
                "direction": "out",
                "reason": "sales",
                "occurred_at": (now - datetime.timedelta(days=1)).isoformat(),
            },
            headers=headers,
        )
        assert out_resp.status_code == 201, out_resp.text

        resp = await client.get(
            "/api/v1/inventory/intelligence/po-suggestions",
            params={
                "lookback_days": 30,
                "lead_time_days": 7,
                "safety_stock_days": 2,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        suggestions = {item["product_id"]: item for item in body.get("suggestions", [])}

        assert product_id in suggestions
        suggestion = suggestions[product_id]
        assert suggestion["recommended_order"] > 0
        assert suggestion["reorder_point"] >= 0
        assert Decimal(str(suggestion["daily_demand"])) > Decimal("0")
        assert Decimal(str(suggestion["purchase_price"])) > Decimal("0")
        assert Decimal(str(suggestion["estimated_cost"])) > Decimal("0")
        assert suggestion["currency"] == "USD"
