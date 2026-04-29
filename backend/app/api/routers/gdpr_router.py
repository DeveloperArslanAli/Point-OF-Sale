"""GDPR Compliance API router.

Provides endpoints for:
- Customer consent management
- Right to access (data export)
- Right to erasure (data deletion)
- Data portability
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.api.dependencies.auth import require_roles, MANAGEMENT_ROLES, ADMIN_ROLE
from app.domain.auth.entities import User, UserRole
from app.infrastructure.db.session import get_session
from app.infrastructure.db.models.customer_model import CustomerModel
from app.domain.common.identifiers import new_ulid

router = APIRouter(prefix="/gdpr", tags=["GDPR Compliance"])


# ==================== Request/Response Models ====================


class ConsentType(BaseModel):
    """Individual consent type."""
    type: str = Field(..., description="Consent type (marketing, analytics, etc.)")
    granted: bool
    granted_at: datetime | None = None


class ConsentUpdateRequest(BaseModel):
    """Request to update customer consent."""
    customer_id: str
    consents: list[ConsentType]


class ConsentStatusResponse(BaseModel):
    """Customer consent status response."""
    customer_id: str
    consents: dict[str, dict]
    last_updated: datetime | None


class DataExportRequest(BaseModel):
    """Request for customer data export."""
    customer_id: str
    format: str = Field("json", pattern="^(json|csv)$")


class DataExportResponse(BaseModel):
    """Data export response."""
    export_id: str
    customer_id: str
    status: str
    download_url: str | None = None
    expires_at: datetime | None = None


class ErasureRequest(BaseModel):
    """Request for customer data erasure."""
    customer_id: str
    reason: str = Field(..., min_length=10, max_length=500)
    verified_identity: bool = Field(..., description="Confirm identity verification")


class ErasureResponse(BaseModel):
    """Erasure request response."""
    request_id: str
    customer_id: str
    status: str
    scheduled_at: datetime
    completed_at: datetime | None = None


# ==================== Endpoints ====================


@router.get("/consent/{customer_id}", response_model=ConsentStatusResponse)
async def get_consent_status(
    customer_id: str,
    _: Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))],
    db: AsyncSession = Depends(get_session),
) -> ConsentStatusResponse:
    """Get current consent status for a customer."""
    customer = await db.get(CustomerModel, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Parse stored consent data
    consent_data = customer.consent_data or {}
    
    return ConsentStatusResponse(
        customer_id=customer_id,
        consents=consent_data,
        last_updated=customer.consent_updated_at,
    )


@router.post("/consent", status_code=status.HTTP_200_OK)
async def update_consent(
    request: ConsentUpdateRequest,
    _: Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))],
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Update customer consent preferences.
    
    Records consent changes with timestamps for audit compliance.
    """
    customer = await db.get(CustomerModel, request.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    now = datetime.now(timezone.utc)
    consent_data = customer.consent_data or {}
    
    for consent in request.consents:
        consent_data[consent.type] = {
            "granted": consent.granted,
            "updated_at": now.isoformat(),
            "previous_value": consent_data.get(consent.type, {}).get("granted"),
        }
    
    customer.consent_data = consent_data
    customer.consent_updated_at = now
    
    await db.commit()
    
    return {
        "success": True,
        "customer_id": request.customer_id,
        "updated_consents": [c.type for c in request.consents],
    }


@router.post("/export", response_model=DataExportResponse)
async def request_data_export(
    request: DataExportRequest,
    background_tasks: BackgroundTasks,
    _: Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))],
    db: AsyncSession = Depends(get_session),
) -> DataExportResponse:
    """Request export of all customer data (GDPR Article 20).
    
    Generates a downloadable file containing all personal data.
    """
    customer = await db.get(CustomerModel, request.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    export_id = new_ulid()
    
    # Schedule background export task
    # In production, this would trigger a Celery task
    # For now, we return a pending status
    
    return DataExportResponse(
        export_id=export_id,
        customer_id=request.customer_id,
        status="processing",
        download_url=None,
        expires_at=None,
    )


@router.post("/erasure", response_model=ErasureResponse)
async def request_data_erasure(
    request: ErasureRequest,
    _: Annotated[User, Depends(require_roles(*ADMIN_ROLE))],
    db: AsyncSession = Depends(get_session),
) -> ErasureResponse:
    """Request erasure of customer data (GDPR Article 17).
    
    Requires admin role and identity verification confirmation.
    Schedules data anonymization while preserving required records.
    """
    if not request.verified_identity:
        raise HTTPException(
            status_code=400,
            detail="Identity verification required before erasure",
        )
    
    customer = await db.get(CustomerModel, request.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    request_id = new_ulid()
    now = datetime.now(timezone.utc)
    
    # Mark customer for erasure
    customer.erasure_requested_at = now
    customer.erasure_reason = request.reason
    
    await db.commit()
    
    # In production, this triggers a Celery task for actual anonymization
    # The task respects legal retention requirements
    
    return ErasureResponse(
        request_id=request_id,
        customer_id=request.customer_id,
        status="scheduled",
        scheduled_at=now,
        completed_at=None,
    )


@router.get("/retention-policy")
async def get_retention_policy(
    _: Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> dict:
    """Get current data retention policy configuration."""
    return {
        "customer_data": {
            "active_retention_days": None,  # Keep while active
            "inactive_retention_days": 365 * 3,  # 3 years after last activity
            "after_erasure_request_days": 30,  # 30 days to complete
        },
        "transaction_data": {
            "retention_years": 7,  # Legal requirement
            "anonymization": "after_retention_period",
        },
        "audit_logs": {
            "retention_years": 5,
            "anonymization": "not_applicable",
        },
        "marketing_data": {
            "retention_after_opt_out_days": 0,  # Immediate deletion
        },
    }


@router.get("/data-inventory")
async def get_data_inventory(
    _: Annotated[User, Depends(require_roles(*ADMIN_ROLE))],
) -> dict:
    """Get inventory of personal data collected (GDPR Article 30).
    
    Returns a record of processing activities.
    """
    return {
        "data_categories": [
            {
                "category": "Identity Data",
                "fields": ["name", "email", "phone"],
                "purpose": "Customer identification and communication",
                "legal_basis": "Contract performance",
                "retention": "Duration of customer relationship + 3 years",
            },
            {
                "category": "Transaction Data",
                "fields": ["purchase_history", "payment_records"],
                "purpose": "Order fulfillment and accounting",
                "legal_basis": "Contract performance, Legal obligation",
                "retention": "7 years (legal requirement)",
            },
            {
                "category": "Marketing Data",
                "fields": ["preferences", "opt-in_status"],
                "purpose": "Marketing communications",
                "legal_basis": "Consent",
                "retention": "Until consent withdrawal",
            },
            {
                "category": "Loyalty Data",
                "fields": ["points_balance", "tier", "rewards_history"],
                "purpose": "Loyalty program administration",
                "legal_basis": "Contract performance",
                "retention": "Duration of membership + 1 year",
            },
        ],
        "third_party_sharing": [
            {
                "recipient": "Payment Processor (Stripe)",
                "data_shared": ["Card token", "Transaction amount"],
                "purpose": "Payment processing",
                "safeguards": "PCI-DSS compliance, Data processing agreement",
            },
        ],
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
