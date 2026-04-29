"""Receipt SQLAlchemy model."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.session import Base


class ReceiptModel(Base):
    """Receipt database model."""

    __tablename__ = "receipts"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    sale_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True, unique=True)
    receipt_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    
    # Store information
    store_name: Mapped[str] = mapped_column(String(200), nullable=False)
    store_address: Mapped[str] = mapped_column(Text, nullable=False)
    store_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    store_tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # People
    cashier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Receipt data (stored as JSON for flexibility)
    line_items: Mapped[dict] = mapped_column(JSON, nullable=False)
    payments: Mapped[dict] = mapped_column(JSON, nullable=False)
    totals: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Sale details
    sale_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    
    # Optional fields
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Format and locale
    format_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="thermal")
    locale: Mapped[str] = mapped_column(String(10), nullable=False, server_default="en_US")
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
