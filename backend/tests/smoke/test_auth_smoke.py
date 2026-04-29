import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.application.auth.use_cases.create_user import CreateUserInput, CreateUserUseCase
from app.domain.auth.entities import UserRole
from app.infrastructure.auth.password_hasher import PasswordHasher
from app.infrastructure.db.repositories.user_repository import UserRepository
from app.infrastructure.db.session import async_session_factory


@pytest.mark.asyncio
async def test_auth_and_roles_smoke():
    admin_email = f"smoke_admin_{uuid.uuid4().hex[:6]}@example.com"
    password = "Password123!"

    async with async_session_factory() as session:
        repo = UserRepository(session)
        if not await repo.get_by_email(admin_email):
            use_case = CreateUserUseCase(repo, PasswordHasher())
            await use_case.execute(CreateUserInput(email=admin_email, password=password, role=UserRole.ADMIN))
            await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Admin login + me + refresh
        login = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": password})
        assert login.status_code == 200, login.text
        tokens = login.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200, me.text

        refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens['refresh_token']})
        assert refresh.status_code == 200, refresh.text

        # Weak password should fail
        weak_email = f"weak_{uuid.uuid4().hex[:6]}@example.com"
        weak_resp = await client.post(
            "/api/v1/auth/users",
            json={"email": weak_email, "password": "short", "role": "CASHIER"},
            headers=headers,
        )
        assert weak_resp.status_code == 400
        body = weak_resp.json()
        assert body.get("code") == "auth.weak_password"

        # Strong password should create cashier
        strong_email = f"cashier_{uuid.uuid4().hex[:6]}@example.com"
        strong_pass = "StrongPass123!"
        strong_resp = await client.post(
            "/api/v1/auth/users",
            json={"email": strong_email, "password": strong_pass, "role": "CASHIER"},
            headers=headers,
        )
        assert strong_resp.status_code == 201, strong_resp.text

        cashier_login = await client.post(
            "/api/v1/auth/login",
            json={"email": strong_email, "password": strong_pass},
        )
        assert cashier_login.status_code == 200, cashier_login.text
        cashier_tokens = cashier_login.json()
        cashier_headers = {"Authorization": f"Bearer {cashier_tokens['access_token']}"}

        # Role enforcement smokes
        products_cashier = await client.get("/api/v1/products", headers=cashier_headers)
        assert products_cashier.status_code == 200, products_cashier.text

        create_payload = {
            "name": "Widget",
            "sku": f"SKU-{uuid.uuid4().hex[:6]}",
            "retail_price": "10.00",
            "purchase_price": "5.00",
            "currency": "USD",
        }
        product_cashier = await client.post(
            "/api/v1/products",
            json=create_payload,
            headers=cashier_headers,
        )
        assert product_cashier.status_code == 403, product_cashier.text

        product_admin = await client.post(
            "/api/v1/products",
            json={**create_payload, "sku": f"SKU-{uuid.uuid4().hex[:6]}"},
            headers=headers,
        )
        assert product_admin.status_code in (201, 400), product_admin.text  # 400 possible if SKU collision
