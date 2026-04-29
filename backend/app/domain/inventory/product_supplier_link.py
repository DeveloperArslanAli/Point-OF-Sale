"""Product-Supplier Link domain entity.

Represents explicit cost/lead time overrides and supplier ranking for products.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.domain.common.identifiers import new_ulid


@dataclass
class ProductSupplierLink:
    """Represents a link between a product and a supplier with pricing/lead time info."""
    
    id: str = field(default_factory=new_ulid)
    product_id: str = ""
    supplier_id: str = ""
    
    # Cost information
    unit_cost: Decimal = Decimal("0")
    currency: str = "USD"
    minimum_order_quantity: int = 1
    
    # Lead time
    lead_time_days: int = 7
    
    # Supplier ranking (lower = preferred)
    priority: int = 1
    is_preferred: bool = False
    
    # Status
    is_active: bool = True
    
    # Notes
    notes: str | None = None
    
    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def calculate_total_cost(self, quantity: int) -> Decimal:
        """Calculate total cost for a given quantity."""
        return self.unit_cost * Decimal(quantity)

    def meets_minimum_order(self, quantity: int) -> bool:
        """Check if quantity meets minimum order requirement."""
        return quantity >= self.minimum_order_quantity
