import datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


@pytest.mark.asyncio
async def test_po_drafts_generate_with_supplier(async_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="admin_phase13_drafts")
        headers = {"Authorization": f"Bearer {admin_token}"}

        now = datetime.datetime.now(datetime.timezone.utc)
        suffix = now.strftime("%Y%m%d%H%M%S%f")

        supplier_resp = await client.post(
            "/api/v1/suppliers",
            json={"name": "Draft Supplier", "contact_email": f"draft{suffix}@example.com"},
            headers=headers,
        )
        assert supplier_resp.status_code == 201, supplier_resp.text
        supplier_id = supplier_resp.json()["id"]

        prod_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "DraftWidget",
                "sku": f"DW-{suffix}",
                "retail_price": "25.00",
                "purchase_price": "10.00",
            },
            headers=headers,
        )
        assert prod_resp.status_code == 201, prod_resp.text
        product_id = prod_resp.json()["id"]

        in_resp = await client.post(
            f"/api/v1/inventory/products/{product_id}/movements",
            json={
                "quantity": 40,
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
                "quantity": 35,
                "direction": "out",
                "reason": "sales",
                "occurred_at": (now - datetime.timedelta(days=1)).isoformat(),
            },
            headers=headers,
        )
        assert out_resp.status_code == 201, out_resp.text

        resp = await client.get(
            "/api/v1/inventory/intelligence/po-drafts",
            params={
                "supplier_id": supplier_id,
                "lookback_days": 30,
                "lead_time_days": 7,
                "safety_stock_days": 2,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["supplier"]["id"] == supplier_id
        lines = body.get("lines", [])
        line_map = {line["product_id"]: line for line in lines}
        assert product_id in line_map
        line = line_map[product_id]
        assert line["quantity"] > 0
        assert Decimal(str(line["unit_cost"])) == Decimal("10.00")
        assert Decimal(str(line["estimated_cost"])) == Decimal(line["quantity"]) * Decimal("10.00")
        assert Decimal(str(body["total_estimated"])) >= Decimal(str(line["estimated_cost"]))
        assert body["currency"] == "USD"


@pytest.mark.asyncio
async def test_po_drafts_respects_budget_cap(async_session):
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(async_session, client, UserRole.ADMIN, email_prefix="admin_phase13_cap")
        headers = {"Authorization": f"Bearer {admin_token}"}

        now = datetime.datetime.now(datetime.timezone.utc)
        suffix = now.strftime("%Y%m%d%H%M%S%f")

        supplier_resp = await client.post(
            "/api/v1/suppliers",
            json={"name": "Cap Supplier", "contact_email": f"cap{suffix}@example.com"},
            headers=headers,
        )
        assert supplier_resp.status_code == 201, supplier_resp.text
        supplier_id = supplier_resp.json()["id"]

        product_ids = []
        for idx in range(3):
            prod_resp = await client.post(
                "/api/v1/products",
                json={
                    "name": f"CapWidget{idx}",
                    "sku": f"CW-{suffix}-{idx}",
                    "retail_price": "30.00",
                    "purchase_price": "12.00",
                },
                headers=headers,
            )
            assert prod_resp.status_code == 201, prod_resp.text
            product_ids.append(prod_resp.json()["id"])

        for pid in product_ids:
            in_resp = await client.post(
                f"/api/v1/inventory/products/{pid}/movements",
                json={
                    "quantity": 50,
                    "direction": "in",
                    "reason": "initial",
                    "occurred_at": (now - datetime.timedelta(days=4)).isoformat(),
                },
                headers=headers,
            )
            assert in_resp.status_code == 201, in_resp.text

            out_resp = await client.post(
                f"/api/v1/inventory/products/{pid}/movements",
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
            "/api/v1/inventory/intelligence/po-drafts",
            params={
                "supplier_id": supplier_id,
                "lookback_days": 30,
                "lead_time_days": 7,
                "safety_stock_days": 2,
                "budget_cap": "150.00",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["budget_cap"] == "150.00"
        assert body["capped"] is True
        assert Decimal(str(body["total_estimated"])) <= Decimal("150.00")
        assert len(body.get("lines", [])) >= 1
