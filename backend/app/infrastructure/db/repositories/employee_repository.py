from __future__ import annotations

from typing import Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import get_current_tenant_id
from app.domain.common.errors import ConflictError
from app.domain.common.money import Money
from app.domain.employees.entities import Employee, EmployeeBonus, SalaryHistory
from app.domain.employees.repositories import EmployeeRepository
from app.infrastructure.db.models.employee_model import (
    EmployeeBonusModel,
    EmployeeModel,
    SalaryHistoryModel,
)


class SqlAlchemyEmployeeRepository(EmployeeRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id and hasattr(EmployeeModel, "tenant_id"):
            return stmt.where(EmployeeModel.tenant_id == tenant_id)
        return stmt

    async def add(self, employee: Employee) -> None:
        tenant_id = get_current_tenant_id()
        model = EmployeeModel(
            id=employee.id,
            first_name=employee.first_name,
            last_name=employee.last_name,
            email=employee.email,
            phone=employee.phone,
            position=employee.position,
            hire_date=employee.hire_date,
            base_salary=employee.base_salary.amount,
            is_active=employee.is_active,
            created_at=employee.created_at,
            updated_at=employee.updated_at,
            tenant_id=tenant_id,
        )
        try:
            self._session.add(model)
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("Employee with this email already exists") from exc

    async def get_by_email(self, email: str) -> Employee | None:
        stmt = select(EmployeeModel).where(EmployeeModel.email == email)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id(self, employee_id: str) -> Employee | None:
        stmt = select(EmployeeModel).where(EmployeeModel.id == employee_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list(
        self,
        page: int = 1,
        limit: int = 20,
        active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Employee], int]:
        query = select(EmployeeModel)
        
        # Apply tenant filter
        query = self._apply_tenant_filter(query)
        
        if active is not None:
            query = query.where(EmployeeModel.is_active == active)
            
        if search:
            search_term = f"%{search}%"
            query = query.where(
                (EmployeeModel.first_name.ilike(search_term)) |
                (EmployeeModel.last_name.ilike(search_term)) |
                (EmployeeModel.email.ilike(search_term))
            )
            
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar_one()
        
        # Pagination
        query = query.offset((page - 1) * limit).limit(limit)
        query = query.order_by(desc(EmployeeModel.created_at))
        
        result = await self._session.execute(query)
        models = result.scalars().all()
        
        return [self._to_entity(m) for m in models], total

    async def update(self, employee: Employee) -> None:
        stmt = select(EmployeeModel).where(EmployeeModel.id == employee.id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one()

        model.first_name = employee.first_name
        model.last_name = employee.last_name
        model.email = employee.email
        model.phone = employee.phone
        model.position = employee.position
        model.base_salary = employee.base_salary.amount
        model.is_active = employee.is_active
        model.updated_at = employee.updated_at

        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("Employee with this email already exists") from exc

    async def add_bonus(self, bonus: EmployeeBonus) -> None:
        model = EmployeeBonusModel(
            id=bonus.id,
            employee_id=bonus.employee_id,
            amount=bonus.amount.amount,
            reason=bonus.reason,
            date_awarded=bonus.date_awarded,
            created_at=bonus.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def add_salary_history(self, history: SalaryHistory) -> None:
        model = SalaryHistoryModel(
            id=history.id,
            employee_id=history.employee_id,
            previous_salary=history.previous_salary.amount,
            new_salary=history.new_salary.amount,
            change_date=history.change_date,
            reason=history.reason,
            created_at=history.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_bonuses(self, employee_id: str) -> list[EmployeeBonus]:
        stmt = (
            select(EmployeeBonusModel)
            .where(EmployeeBonusModel.employee_id == employee_id)
            .order_by(desc(EmployeeBonusModel.date_awarded))
        )
        result = await self._session.execute(stmt)
        return [self._to_bonus_entity(m) for m in result.scalars().all()]

    async def get_salary_history(self, employee_id: str) -> list[SalaryHistory]:
        stmt = (
            select(SalaryHistoryModel)
            .where(SalaryHistoryModel.employee_id == employee_id)
            .order_by(desc(SalaryHistoryModel.change_date))
        )
        result = await self._session.execute(stmt)
        return [self._to_history_entity(m) for m in result.scalars().all()]

    def _to_entity(self, model: EmployeeModel) -> Employee:
        return Employee(
            id=model.id,
            first_name=model.first_name,
            last_name=model.last_name,
            email=model.email,
            phone=model.phone,
            position=model.position,
            hire_date=model.hire_date,
            base_salary=Money(model.base_salary),
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_bonus_entity(self, model: EmployeeBonusModel) -> EmployeeBonus:
        return EmployeeBonus(
            id=model.id,
            employee_id=model.employee_id,
            amount=Money(model.amount),
            reason=model.reason,
            date_awarded=model.date_awarded,
            created_at=model.created_at,
        )

    def _to_history_entity(self, model: SalaryHistoryModel) -> SalaryHistory:
        return SalaryHistory(
            id=model.id,
            employee_id=model.employee_id,
            previous_salary=Money(model.previous_salary),
            new_salary=Money(model.new_salary),
            change_date=model.change_date,
            reason=model.reason,
            created_at=model.created_at,
        )
