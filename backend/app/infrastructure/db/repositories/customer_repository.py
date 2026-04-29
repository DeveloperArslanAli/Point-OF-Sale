from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.customers.ports import CustomerRepository
from app.core.encryption import decrypt_pii, encrypt_pii
from app.core.tenant import get_current_tenant_id
from app.domain.customers import Customer
from app.infrastructure.db.models.customer_model import CustomerModel


class SqlAlchemyCustomerRepository(CustomerRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id and hasattr(CustomerModel, "tenant_id"):
            return stmt.where(CustomerModel.tenant_id == tenant_id)
        return stmt

    async def add(self, customer: Customer) -> None:
        tenant_id = get_current_tenant_id()
        model = CustomerModel(
            id=customer.id,
            first_name=customer.first_name,
            last_name=customer.last_name,
            email=customer.email,
            phone=encrypt_pii(customer.phone),  # Encrypt PII
            active=customer.active,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
            version=customer.version,
            tenant_id=tenant_id,  # Set tenant from context
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_email(self, email: str) -> Customer | None:
        stmt = select(CustomerModel).where(CustomerModel.email == email.lower())
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id(self, customer_id: str) -> Customer | None:
        stmt = select(CustomerModel).where(CustomerModel.id == customer_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_customers(
        self,
        *,
        search: str | None = None,
        active: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Customer], int]:
        stmt = select(CustomerModel)
        count_stmt = select(func.count(CustomerModel.id))
        
        # Apply tenant filter
        stmt = self._apply_tenant_filter(stmt)
        count_stmt = self._apply_tenant_filter(count_stmt)

        filters = []
        if search:
            like = f"%{search.lower()}%"
            filters.append(
                or_(
                    func.lower(CustomerModel.first_name).like(like),
                    func.lower(CustomerModel.last_name).like(like),
                    func.lower(CustomerModel.email).like(like),
                )
            )
        if active is not None:
            filters.append(CustomerModel.active == active)

        for condition in filters:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        stmt = stmt.order_by(CustomerModel.created_at.desc()).offset(offset).limit(limit)

        rows = (await self._session.execute(stmt)).scalars().all()
        total = (await self._session.execute(count_stmt)).scalar_one()
        customers: list[Customer] = []
        for row in rows:
            customer = self._to_entity(row)
            if customer is not None:
                customers.append(customer)
        return customers, int(total)

    async def update(self, customer: Customer, *, expected_version: int) -> bool:
        stmt = (
            update(CustomerModel)
            .where(CustomerModel.id == customer.id, CustomerModel.version == expected_version)
            .values(
                first_name=customer.first_name,
                last_name=customer.last_name,
                email=customer.email,
                phone=encrypt_pii(customer.phone),  # Encrypt PII
                active=customer.active,
                updated_at=customer.updated_at,
                version=customer.version,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    def _to_entity(self, model: CustomerModel | None) -> Customer | None:
        if model is None:
            return None
        return Customer(
            id=model.id,
            first_name=model.first_name,
            last_name=model.last_name,
            email=model.email,
            phone=decrypt_pii(model.phone),  # Decrypt PII
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )
