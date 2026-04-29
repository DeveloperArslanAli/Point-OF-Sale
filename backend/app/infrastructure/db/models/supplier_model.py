from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.product_supplier_link_model import ProductSupplierLinkModel


class SupplierModel(Base):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)

    # Relationships
    product_links: Mapped[List["ProductSupplierLinkModel"]] = relationship(
        "ProductSupplierLinkModel",
        back_populates="supplier",
        cascade="all, delete-orphan",
    )
