import datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


@pytest.mark.asyncio
async def test_inventory_abc_classifies_products(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_phase13_abc")
        headers = {"Authorization": f"Bearer {manager_token}"}

        now = datetime.datetime.now(datetime.timezone.utc)
        suffix = now.strftime("%Y%m%d%H%M%S%f")

        async def create_product(name: str, sku: str, retail_price: str, purchase_price: str) -> str:
            resp = await client.post(
                "/api/v1/products",
                json={
                    "name": name,
                    "sku": sku,
                    "retail_price": retail_price,
                    "purchase_price": purchase_price,
                },
                headers=headers,
            )
            assert resp.status_code == 201, resp.text
            return resp.json()["id"]

        p_a = await create_product("WidgetA", f"WA-{suffix}", "100.00", "10.00")
        p_b = await create_product("WidgetB", f"WB-{suffix}", "100.00", "10.00")
        p_c = await create_product("WidgetC", f"WC-{suffix}", "100.00", "10.00")

        async def seed_movement(product_id: str, quantity: int):
            in_resp = await client.post(
                f"/api/v1/inventory/products/{product_id}/movements",
                json={
                    "quantity": quantity,
                    "direction": "in",
                    "reason": "seed",
                    "occurred_at": (now - datetime.timedelta(hours=3)).isoformat(),
                },
                headers=headers,
            )
            assert in_resp.status_code == 201, in_resp.text

            out_resp = await client.post(
                f"/api/v1/inventory/products/{product_id}/movements",
                json={
                    "quantity": quantity,
                    "direction": "out",
                    "reason": "sale",
                    "occurred_at": (now - datetime.timedelta(hours=2)).isoformat(),
                },
                headers=headers,
            )
            assert out_resp.status_code == 201, out_resp.text

        await seed_movement(p_a, 60000)  # usage value 6,000,000
        await seed_movement(p_b, 30000)  # usage value 3,000,000
        await seed_movement(p_c, 10000)  # usage value 1,000,000

        resp = await client.get(
            "/api/v1/inventory/intelligence/abc",
            params={
                    "lookback_days": 30,
                "a_threshold_percent": 70,
                "b_threshold_percent": 90,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        classes = body.get("classifications", [])
        by_product = {item["product_id"]: item for item in classes if item["product_id"] in {p_a, p_b, p_c}}

        assert len(by_product) == 3

        assert by_product[p_a]["abc_class"] == "A"
        assert by_product[p_b]["abc_class"] == "B"
        assert by_product[p_c]["abc_class"] == "C"

        a_pct = Decimal(str(by_product[p_a]["cumulative_percent"]))
        b_pct = Decimal(str(by_product[p_b]["cumulative_percent"]))
        c_pct = Decimal(str(by_product[p_c]["cumulative_percent"]))

        assert a_pct <= Decimal("70")
        assert Decimal("70") < b_pct <= Decimal("90")
        assert c_pct > Decimal("90")
