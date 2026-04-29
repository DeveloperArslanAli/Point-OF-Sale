from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base
from app.infrastructure.db.utils import utcnow


class EmployeeModel(Base):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    position: Mapped[str] = mapped_column(String(100))
    hire_date: Mapped[date] = mapped_column(Date)
    base_salary: Mapped[float] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)

    bonuses: Mapped[list[EmployeeBonusModel]] = relationship(back_populates="employee", cascade="all, delete-orphan")
    salary_history: Mapped[list[SalaryHistoryModel]] = relationship(back_populates="employee", cascade="all, delete-orphan")


class EmployeeBonusModel(Base):
    __tablename__ = "employee_bonuses"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(26), ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    reason: Mapped[str] = mapped_column(String(255))
    date_awarded: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    employee: Mapped[EmployeeModel] = relationship(back_populates="bonuses")


class SalaryHistoryModel(Base):
    __tablename__ = "salary_history"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(26), ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    previous_salary: Mapped[float] = mapped_column(Numeric(12, 2))
    new_salary: Mapped[float] = mapped_column(Numeric(12, 2))
    change_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    employee: Mapped[EmployeeModel] = relationship(back_populates="salary_history")
