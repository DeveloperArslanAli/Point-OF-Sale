from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.tenant import get_current_tenant_id
from app.domain.auth.entities import User, UserRole
from app.infrastructure.db.models.auth.user_model import UserModel
from app.shared.pagination import PageParams


class UserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    def _apply_tenant_filter(self, stmt: Select[Any]) -> Select[Any]:
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(UserModel.tenant_id == tenant_id)
        return stmt

    async def add(self, user: User) -> None:
        model = UserModel(
            id=user.id,
            tenant_id=user.tenant_id or get_current_tenant_id(),
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
            active=user.active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            version=user.version,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email.lower())
        # Note: email lookup doesn't filter by tenant for login purposes
        res = await self._session.execute(stmt)
        m = res.scalar_one_or_none()
        if m is None:
            return None
        return self._to_domain(m)

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        stmt = self._apply_tenant_filter(stmt)
        res = await self._session.execute(stmt)
        m = res.scalar_one_or_none()
        if m is None:
            return None
        return self._to_domain(m)

    async def update(self, user: User, expected_version: int) -> bool:
        stmt = (
            update(UserModel)
            .where(UserModel.id == user.id, UserModel.version == expected_version)
            .values(
                email=user.email,
                password_hash=user.password_hash,
                role=user.role,
                active=user.active,
                updated_at=user.updated_at,
                version=user.version,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount == 1

    async def search(
        self,
        *,
        email: str | None,
        role: UserRole | None,
        active: bool | None,
        params: PageParams,
    ) -> tuple[list[User], int]:
        stmt = select(UserModel)
        count_stmt: Select[Any] = select(func.count(UserModel.id))
        
        # Apply tenant filter
        stmt = self._apply_tenant_filter(stmt)
        tenant_id = get_current_tenant_id()
        if tenant_id:
            count_stmt = count_stmt.where(UserModel.tenant_id == tenant_id)
        
        conditions: list[ColumnElement[bool]] = []
        if email:
            conditions.append(UserModel.email.ilike(f"%{email.lower()}%"))
        if role:
            conditions.append(UserModel.role == role)
        if active is not None:
            conditions.append(UserModel.active == active)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        stmt = (
            stmt.order_by(UserModel.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        items = [self._to_domain(model) for model in models]

        total_result = await self._session.execute(count_stmt)
        total = int(total_result.scalar_one())
        return items, total

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            role=UserRole(model.role),
            active=model.active,
            tenant_id=model.tenant_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )