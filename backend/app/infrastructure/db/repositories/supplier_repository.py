from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.suppliers.ports import SupplierRepository
from app.core.tenant import get_current_tenant_id
from app.domain.suppliers import Supplier
from app.infrastructure.db.models.supplier_model import SupplierModel


class SqlAlchemySupplierRepository(SupplierRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id and hasattr(SupplierModel, "tenant_id"):
            return stmt.where(SupplierModel.tenant_id == tenant_id)
        return stmt

    async def add(self, supplier: Supplier) -> None:
        tenant_id = get_current_tenant_id()
        model = SupplierModel(
            id=supplier.id,
            name=supplier.name,
            contact_email=supplier.contact_email,
            contact_phone=supplier.contact_phone,
            active=supplier.active,
            created_at=supplier.created_at,
            updated_at=supplier.updated_at,
            version=supplier.version,
            tenant_id=tenant_id,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, supplier_id: str) -> Supplier | None:
        stmt = select(SupplierModel).where(SupplierModel.id == supplier_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model)

    async def get_by_email(self, email: str) -> Supplier | None:
        stmt = select(SupplierModel).where(SupplierModel.contact_email == email.lower())
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model)

    async def list_suppliers(
        self,
        *,
        search: str | None = None,
        active: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Supplier], int]:
        stmt = select(SupplierModel)
        count_stmt = select(func.count(SupplierModel.id))
        
        # Apply tenant filter
        stmt = self._apply_tenant_filter(stmt)
        count_stmt = self._apply_tenant_filter(count_stmt)

        conditions = []
        if search:
            like = f"%{search.lower()}%"
            conditions.append(
                or_(
                    func.lower(SupplierModel.name).like(like),
                    func.lower(SupplierModel.contact_email).like(like),
                )
            )
        if active is not None:
            conditions.append(SupplierModel.active == active)

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        stmt = stmt.order_by(SupplierModel.created_at.desc()).offset(offset).limit(limit)

        rows_result = await self._session.execute(stmt)
        rows = rows_result.scalars().all()
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()
        suppliers: list[Supplier] = []
        for row in rows:
            supplier = self._to_entity(row)
            if supplier is not None:
                suppliers.append(supplier)
        return suppliers, int(total)

    def _to_entity(self, model: SupplierModel | None) -> Supplier | None:
        if model is None:
            return None
        return Supplier(
            id=model.id,
            name=model.name,
            contact_email=model.contact_email,
            contact_phone=model.contact_phone,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )
