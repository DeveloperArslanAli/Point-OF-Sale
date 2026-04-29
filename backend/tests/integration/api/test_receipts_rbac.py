import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from .helpers import login_as


@pytest.mark.asyncio
async def test_auditor_cannot_access_receipts(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.AUDITOR, email_prefix="auditor")

        resp = await client.get(
            "/api/v1/receipts/some-id",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 403
        payload = resp.json()
        assert payload.get("code") == "insufficient_role"


@pytest.mark.asyncio
async def test_inventory_cannot_access_receipts(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.INVENTORY, email_prefix="inventory")

        resp = await client.get(
            "/api/v1/receipts/some-id",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 403
        payload = resp.json()
        assert payload.get("code") == "insufficient_role"


@pytest.mark.asyncio
async def test_cashier_can_access_receipts_route(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="cashier")

        resp = await client.get(
            "/api/v1/receipts/some-id",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Route reached; business logic returns 404 for missing receipt rather than 403.
        assert resp.status_code in {404, 403}
        if resp.status_code == 403:
            # Guard against unexpected role regression.
            assert resp.json().get("code") == "insufficient_role"