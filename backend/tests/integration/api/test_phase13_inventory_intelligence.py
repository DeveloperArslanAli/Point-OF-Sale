import datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


@pytest.mark.asyncio
async def test_inventory_intelligence_returns_low_and_dead_stock(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_phase13")
        headers = {"Authorization": f"Bearer {manager_token}"}

        now = datetime.datetime.now(datetime.timezone.utc)
        suffix = now.strftime("%Y%m%d%H%M%S%f")

        # Product likely to trigger low-stock recommendation
        p1_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "ForecastWidget",
                "sku": f"FW-{suffix}",
                "retail_price": "10.00",
                "purchase_price": "5.00",
            },
            headers=headers,
        )
        assert p1_resp.status_code == 201, p1_resp.text
        p1_id = p1_resp.json()["id"]

        # Seed stock in and recent outflow
        in_move = await client.post(
            f"/api/v1/inventory/products/{p1_id}/movements",
            json={
                "quantity": 10,
                "direction": "in",
                "reason": "initial",
                "occurred_at": (now - datetime.timedelta(days=5)).isoformat(),
            },
            headers=headers,
        )
        assert in_move.status_code == 201, in_move.text

        out_move = await client.post(
            f"/api/v1/inventory/products/{p1_id}/movements",
            json={
                "quantity": 8,
                "direction": "out",
                "reason": "sale",
                "occurred_at": (now - datetime.timedelta(days=2)).isoformat(),
            },
            headers=headers,
        )
        assert out_move.status_code == 201, out_move.text

        # Product with stale stock to flag as dead stock
        p2_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "OldWidget",
                "sku": f"OW-{suffix}",
                "retail_price": "15.00",
                "purchase_price": "7.00",
            },
            headers=headers,
        )
        assert p2_resp.status_code == 201, p2_resp.text
        p2_id = p2_resp.json()["id"]

        dead_move = await client.post(
            f"/api/v1/inventory/products/{p2_id}/movements",
            json={
                "quantity": 5,
                "direction": "in",
                "reason": "initial",
                "occurred_at": (now - datetime.timedelta(days=120)).isoformat(),
            },
            headers=headers,
        )
        assert dead_move.status_code == 201, dead_move.text

        insights_resp = await client.get(
            "/api/v1/inventory/intelligence",
            params={
                "lookback_days": 30,
                "lead_time_days": 7,
                "safety_stock_days": 2,
                "dead_stock_days": 90,
            },
            headers=headers,
        )
        assert insights_resp.status_code == 200, insights_resp.text
        body = insights_resp.json()

        low_stock = {item["product_id"]: item for item in body.get("low_stock", [])}
        dead_stock = {item["product_id"]: item for item in body.get("dead_stock", [])}

        assert p1_id in low_stock
        p1_insight = low_stock[p1_id]
        assert p1_insight["reorder_point"] > p1_insight["quantity_on_hand"]
        assert p1_insight["recommended_order"] >= 1
        assert Decimal(str(p1_insight["daily_demand"])) > Decimal("0")

        assert p2_id in dead_stock
        assert dead_stock[p2_id]["days_since_movement"] >= 90
