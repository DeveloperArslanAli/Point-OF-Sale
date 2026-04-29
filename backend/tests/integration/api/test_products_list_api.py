from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.main import app
from app.application.catalog.use_cases.create_product import (
    CreateProductInput,
    CreateProductUseCase,
)
from app.domain.auth.entities import UserRole
from app.infrastructure.db.models.product_model import ProductModel
from app.infrastructure.db.repositories.inventory_repository import SqlAlchemyProductRepository
from app.infrastructure.db.session import AsyncSessionLocal
from app.api.dependencies.cache import _memory_cache
from tests.integration.api.helpers import create_user_and_login


async def ensure_seed(target: int = 5):
    # Invalidate product list cache so new seeds are visible during tests
    await _memory_cache.clear_prefix("products:list")
    async with AsyncSessionLocal() as session:
        repo = SqlAlchemyProductRepository(session)
        uc = CreateProductUseCase(repo)
        existing_skus = set((await session.execute(select(ProductModel.sku))).scalars())
        created = False
        for i in range(1, target + 1):
            sku = f"SKU{i}"
            if sku in existing_skus:
                continue
            await uc.execute(
                CreateProductInput(
                    name=f"Prod {i}",
                    sku=sku,
                    retail_price=Decimal(str(10 + i)),
                    purchase_price=Decimal("5.00"),
                )
            )
            created = True
        if created:
            await session.commit()


async def create_custom_product(
    name: str,
    sku: str,
    retail_price: Decimal,
    purchase_price: Decimal = Decimal("5.00"),
) -> None:
    async with AsyncSessionLocal() as session:
        repo = SqlAlchemyProductRepository(session)
        uc = CreateProductUseCase(repo)
        await uc.execute(
            CreateProductInput(
                name=name,
                sku=sku,
                retail_price=retail_price,
                purchase_price=purchase_price,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_list_products_basic_pagination(async_session):
    await ensure_seed()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await create_user_and_login(
            async_session,
            client,
            f"sales_viewer_{uuid4().hex[:6]}@example.com",
            "Secretp@ss1",
            UserRole.CASHIER,
        )
        resp = await client.get(
            "/api/v1/products",
            params={"page": 1, "limit": 2},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["meta"]["total"] >= 5
        assert data["meta"]["page"] == 1
    assert data["meta"]["pages"] >= 1


@pytest.mark.asyncio
async def test_list_products_search(async_session):
    await ensure_seed()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await create_user_and_login(
            async_session,
            client,
            f"sales_search_{uuid4().hex[:6]}@example.com",
            "Secretp@ss1",
            UserRole.CASHIER,
        )
        resp = await client.get(
            "/api/v1/products",
            params={"search": "Prod 3"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["name"] == "Prod 3" for item in data["items"])  # ensure search hit


@pytest.mark.asyncio
async def test_list_products_price_filter(async_session):
    await ensure_seed()
    await create_custom_product("Premium", f"SKU{uuid4().hex[:6]}", Decimal("125.00"))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await create_user_and_login(
            async_session,
            client,
            f"sales_price_{uuid4().hex[:6]}@example.com",
            "Secretp@ss1",
            UserRole.CASHIER,
        )
        resp = await client.get(
            "/api/v1/products",
            params={"min_price": "100", "sort_by": "retail_price", "sort_direction": "asc"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"], "Expected at least one item above min price"
        for item in data["items"]:
            assert Decimal(item["retail_price"]) >= Decimal("100")


@pytest.mark.asyncio
async def test_list_products_invalid_price_range(async_session):
    await ensure_seed()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await create_user_and_login(
            async_session,
            client,
            f"sales_invalid_{uuid4().hex[:6]}@example.com",
            "Secretp@ss1",
            UserRole.CASHIER,
        )
        resp = await client.get(
            "/api/v1/products",
            params={"min_price": "50", "max_price": "10"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "min_price" in resp.text


@pytest.mark.asyncio
async def test_list_products_sort_by_name(async_session):
    await ensure_seed()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await create_user_and_login(
            async_session,
            client,
            f"sales_sort_{uuid4().hex[:6]}@example.com",
            "Secretp@ss1",
            UserRole.CASHIER,
        )
        resp = await client.get(
            "/api/v1/products",
            params={"limit": 5, "sort_by": "name", "sort_direction": "asc"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        names = [item["name"] for item in data["items"]]
        assert names == sorted(names, key=str.lower)
