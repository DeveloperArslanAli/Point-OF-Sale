from __future__ import annotations

from typing import Protocol

from app.domain.employees.entities import Employee, EmployeeBonus, SalaryHistory


class EmployeeRepository(Protocol):
    async def add(self, employee: Employee) -> None:
        ...

    async def get_by_id(self, employee_id: str) -> Employee | None:
        ...

    async def get_by_email(self, email: str) -> Employee | None:
        ...

    async def list(
        self,
        page: int = 1,
        limit: int = 20,
        active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Employee], int]:
        ...

    async def update(self, employee: Employee) -> None:
        ...

    async def add_bonus(self, bonus: EmployeeBonus) -> None:
        ...

    async def add_salary_history(self, history: SalaryHistory) -> None:
        ...

    async def get_bonuses(self, employee_id: str) -> list[EmployeeBonus]:
        ...

    async def get_salary_history(self, employee_id: str) -> list[SalaryHistory]:
        ...
