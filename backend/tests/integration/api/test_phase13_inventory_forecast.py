import datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


@pytest.mark.asyncio
async def test_inventory_forecast_returns_stockout_projection(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_phase13_forecast")
        headers = {"Authorization": f"Bearer {manager_token}"}

        now = datetime.datetime.now(datetime.timezone.utc)
        suffix = now.strftime("%Y%m%d%H%M%S%f")

        # Product with steady demand to forecast
        prod_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "ForecastedWidget",
                "sku": f"FC-{suffix}",
                "retail_price": "12.00",
                "purchase_price": "6.00",
            },
            headers=headers,
        )
        assert prod_resp.status_code == 201, prod_resp.text
        product_id = prod_resp.json()["id"]

        # Seed stock and outflows within lookback
        in_resp = await client.post(
            f"/api/v1/inventory/products/{product_id}/movements",
            json={
                "quantity": 100,
                "direction": "in",
                "reason": "initial",
                "occurred_at": (now - datetime.timedelta(days=2)).isoformat(),
            },
            headers=headers,
        )
        assert in_resp.status_code == 201, in_resp.text

        out_resp = await client.post(
            f"/api/v1/inventory/products/{product_id}/movements",
            json={
                "quantity": 50,
                "direction": "out",
                "reason": "sales",
                "occurred_at": (now - datetime.timedelta(days=1)).isoformat(),
            },
            headers=headers,
        )
        assert out_resp.status_code == 201, out_resp.text

        resp = await client.get(
            "/api/v1/inventory/intelligence/forecast",
            params={
                "lookback_days": 60,
                "lead_time_days": 7,
                "safety_stock_days": 2,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        forecasts = {item["product_id"]: item for item in body.get("forecasts", [])}

        assert body.get("expires_at")
        assert body.get("ttl_minutes") >= 30
        assert body.get("stale") is False

        assert product_id in forecasts
        forecast = forecasts[product_id]

        # daily demand should reflect 50 units over 60 days (~0.83)
        assert Decimal(str(forecast["daily_demand"])) > Decimal("0.5")
        assert forecast["days_until_stockout"] > 0
        assert forecast["recommended_order"] >= 0
        assert forecast["projected_stockout_date"] is not None
        assert forecast["recommended_reorder_date"] is not None
