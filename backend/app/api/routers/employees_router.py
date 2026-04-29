from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import ADMIN_ROLE, MANAGEMENT_ROLES, require_roles
from app.infrastructure.db.session import get_session
from app.shared.pagination import Page, PageParams
from app.domain.common.errors import ConflictError
from app.domain.common.errors import DomainError
from app.api.schemas.employee import (
    BonusCreate,
    BonusOut,
    EmployeeCreate,
    EmployeeOut,
    EmployeeUpdate,
    IncrementCreate,
    SalaryHistoryOut,
)
from app.application.auth.use_cases.create_user import CreateUserInput, CreateUserUseCase
from app.domain.auth.entities import User, UserRole
from app.domain.common.money import Money
from app.domain.employees.entities import Employee
from app.infrastructure.auth.password_hasher import PasswordHasher
from app.infrastructure.db.repositories.employee_repository import SqlAlchemyEmployeeRepository
from app.infrastructure.db.repositories.user_repository import UserRepository

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*ADMIN_ROLE)),
) -> EmployeeOut:
    repo = SqlAlchemyEmployeeRepository(session)
    existing = await repo.get_by_email(payload.email)
    if existing:
        raise ConflictError("Employee with this email already exists")
    
    # Check if user creation is requested and validate
    if payload.create_user_account:
        if not payload.password:
            raise HTTPException(status_code=400, detail="Password is required when creating a user account")
        if not payload.role:
            raise HTTPException(status_code=400, detail="Role is required when creating a user account")

    employee = Employee.create(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        position=payload.position,
        hire_date=payload.hire_date,
        base_salary=Money(payload.base_salary),
    )
    
    await repo.add(employee)
    
    # Create user account if requested
    if payload.create_user_account:
        user_repo = UserRepository(session)
        hasher = PasswordHasher()
        use_case = CreateUserUseCase(user_repo, hasher)

        try:
            role_enum = UserRole(payload.role.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {payload.role}")

        try:
            await use_case.execute(
                CreateUserInput(
                    email=payload.email,
                    password=payload.password,  # type: ignore
                    role=role_enum,
                )
            )
        except ConflictError:
            # Let domain conflict bubble to middleware for a 409 response
            raise
        except DomainError:
            # Preserve domain errors (e.g., validation) for middleware handling
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to create user account: {str(e)}")

    return _map_employee(employee)


@router.get("", response_model=Page[EmployeeOut])
async def list_employees(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    active: bool | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> Any:
    repo = SqlAlchemyEmployeeRepository(session)
    employees, total = await repo.list(page=page, limit=limit, active=active, search=search)
    
    items = [_map_employee(e) for e in employees]
    return Page.build(items, total, PageParams(page=page, limit=limit))


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> EmployeeOut:
    repo = SqlAlchemyEmployeeRepository(session)
    employee = await repo.get_by_id(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return _map_employee(employee)


@router.patch("/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: str,
    payload: EmployeeUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*ADMIN_ROLE)),
) -> EmployeeOut:
    repo = SqlAlchemyEmployeeRepository(session)
    employee = await repo.get_by_id(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if payload.email and payload.email != employee.email:
        duplicate = await repo.get_by_email(payload.email)
        if duplicate:
            raise ConflictError("Employee with this email already exists")
        
    employee.update(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        position=payload.position,
        is_active=payload.is_active,
    )
    
    await repo.update(employee)
    return _map_employee(employee)


@router.post("/{employee_id}/increment", response_model=SalaryHistoryOut)
async def grant_increment(
    employee_id: str,
    payload: IncrementCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*ADMIN_ROLE)),
) -> SalaryHistoryOut:
    repo = SqlAlchemyEmployeeRepository(session)
    employee = await repo.get_by_id(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    history = employee.change_salary(
        new_salary=Money(payload.new_salary),
        reason=payload.reason,
        change_date=payload.change_date,
    )
    
    await repo.update(employee)
    await repo.add_salary_history(history)
    
    return SalaryHistoryOut(
        id=history.id,
        employee_id=history.employee_id,
        previous_salary=history.previous_salary.amount,
        new_salary=history.new_salary.amount,
        change_date=history.change_date,
        reason=history.reason,
        created_at=history.created_at,
    )


@router.post("/{employee_id}/bonus", response_model=BonusOut)
async def give_bonus(
    employee_id: str,
    payload: BonusCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*ADMIN_ROLE)),
) -> BonusOut:
    repo = SqlAlchemyEmployeeRepository(session)
    employee = await repo.get_by_id(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    bonus = employee.give_bonus(
        amount=Money(payload.amount),
        reason=payload.reason,
        date_awarded=payload.date_awarded,
    )
    
    await repo.add_bonus(bonus)
    
    return BonusOut(
        id=bonus.id,
        employee_id=bonus.employee_id,
        amount=bonus.amount.amount,
        reason=bonus.reason,
        date_awarded=bonus.date_awarded,
        created_at=bonus.created_at,
    )


@router.get("/{employee_id}/financial-history", response_model=dict[str, Any])
async def get_financial_history(
    employee_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> dict[str, Any]:
    repo = SqlAlchemyEmployeeRepository(session)
    employee = await repo.get_by_id(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    bonuses = await repo.get_bonuses(employee_id)
    salary_history = await repo.get_salary_history(employee_id)
    
    return {
        "bonuses": [
            BonusOut(
                id=b.id,
                employee_id=b.employee_id,
                amount=b.amount.amount,
                reason=b.reason,
                date_awarded=b.date_awarded,
                created_at=b.created_at,
            ) for b in bonuses
        ],
        "salary_history": [
            SalaryHistoryOut(
                id=h.id,
                employee_id=h.employee_id,
                previous_salary=h.previous_salary.amount,
                new_salary=h.new_salary.amount,
                change_date=h.change_date,
                reason=h.reason,
                created_at=h.created_at,
            ) for h in salary_history
        ]
    }


def _map_employee(e: Employee) -> EmployeeOut:
    return EmployeeOut(
        id=e.id,
        first_name=e.first_name,
        last_name=e.last_name,
        email=e.email,
        phone=e.phone,
        position=e.position,
        hire_date=e.hire_date,
        base_salary=e.base_salary.amount,
        is_active=e.is_active,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )
