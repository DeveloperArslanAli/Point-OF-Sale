from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.catalog.ports import CategoryRepository
from app.core.tenant import get_current_tenant_id
from app.domain.catalog.entities import Category
from app.infrastructure.db.models.category_model import CategoryModel


class SqlAlchemyCategoryRepository(CategoryRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id and hasattr(CategoryModel, "tenant_id"):
            return stmt.where(CategoryModel.tenant_id == tenant_id)
        return stmt

    async def add(self, category: Category) -> None:
        tenant_id = get_current_tenant_id()
        model = CategoryModel(
            id=category.id,
            name=category.name,
            slug=category.slug,
            description=category.description,
            created_at=category.created_at,
            updated_at=category.updated_at,
            version=category.version,
            tenant_id=tenant_id,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_slug(self, slug: str) -> Category | None:
        stmt = select(CategoryModel).where(CategoryModel.slug == slug)
        stmt = self._apply_tenant_filter(stmt)
        res = await self._session.execute(stmt)
        model = res.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id(self, category_id: str) -> Category | None:
        stmt = select(CategoryModel).where(CategoryModel.id == category_id)
        stmt = self._apply_tenant_filter(stmt)
        res = await self._session.execute(stmt)
        model = res.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def search(
        self,
        *,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Category], int]:
        stmt = select(CategoryModel)
        count_stmt = select(func.count(CategoryModel.id))
        
        # Apply tenant filter
        stmt = self._apply_tenant_filter(stmt)
        count_stmt = self._apply_tenant_filter(count_stmt)
        
        if search:
            pattern = f"%{search}%"
            search_clause = or_(
                CategoryModel.name.ilike(pattern),
                CategoryModel.slug.ilike(pattern),
            )
            stmt = stmt.where(search_clause)
            count_stmt = count_stmt.where(search_clause)

        stmt = (
            stmt.order_by(CategoryModel.name.asc())
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        total_result = await self._session.execute(count_stmt)
        total = int(total_result.scalar_one())
        return [self._to_entity(m) for m in models], total

    def _to_entity(self, model: CategoryModel) -> Category:
        return Category(
            id=model.id,
            name=model.name,
            slug=model.slug,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )
