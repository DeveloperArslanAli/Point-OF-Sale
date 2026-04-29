"""Receipt API router."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import SALES_ROLES, require_roles
from app.api.schemas.receipt import (
    CreateReceiptRequest,
    MoneySchema,
    ReceiptLineItemSchema,
    ReceiptListResponse,
    ReceiptPaymentSchema,
    ReceiptResponse,
    ReceiptTotalsSchema,
)
from app.application.receipts import (
    CreateReceipt,
    GetReceipt,
    GetReceiptBySaleId,
    GetReceiptByNumber,
    ListReceiptsByDateRange,
)
from app.domain.auth.entities import User
from app.domain.common.money import Money
from app.domain.common.errors import NotFoundError
from app.domain.receipts import Receipt, ReceiptLineItem, ReceiptPayment, ReceiptTotals
from app.infrastructure.db.repositories.receipt_repository import ReceiptRepository
from app.infrastructure.db.session import get_session
from app.infrastructure.services.receipt_pdf_generator import ReceiptPDFGenerator
from app.infrastructure.tasks.email_tasks import send_receipt_email

router = APIRouter(prefix="/receipts", tags=["receipts"])


def get_receipt_repository(
    session: Annotated[AsyncSession, Depends(get_session)]
) -> ReceiptRepository:
    """Get receipt repository dependency."""
    return ReceiptRepository(session)


def get_pdf_generator() -> ReceiptPDFGenerator:
    """Get PDF generator dependency."""
    return ReceiptPDFGenerator()


@router.post("", response_model=ReceiptResponse, status_code=201)
async def create_receipt(
    request: CreateReceiptRequest,
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
    receipt_repository: Annotated[ReceiptRepository, Depends(get_receipt_repository)],
) -> ReceiptResponse:
    """Create a new receipt."""
    # Role check is performed by dependency injection above.

    # Convert schema to domain objects
    line_items = [
        ReceiptLineItem(
            product_name=item.product_name,
            sku=item.sku,
            quantity=item.quantity,
            unit_price=Money(item.unit_price.amount, item.unit_price.currency),
            line_total=Money(item.line_total.amount, item.line_total.currency),
            discount_amount=Money(item.discount_amount.amount, item.discount_amount.currency),
        )
        for item in request.line_items
    ]
    
    payments = [
        ReceiptPayment(
            payment_method=payment.payment_method,
            amount=Money(payment.amount.amount, payment.amount.currency),
            reference_number=payment.reference_number,
            card_last_four=payment.card_last_four,
        )
        for payment in request.payments
    ]
    
    totals = ReceiptTotals(
        subtotal=Money(request.totals.subtotal.amount, request.totals.subtotal.currency),
        tax_amount=Money(request.totals.tax_amount.amount, request.totals.tax_amount.currency),
        discount_amount=Money(request.totals.discount_amount.amount, request.totals.discount_amount.currency),
        total=Money(request.totals.total.amount, request.totals.total.currency),
        amount_paid=Money(request.totals.amount_paid.amount, request.totals.amount_paid.currency),
        change_given=Money(request.totals.change_given.amount, request.totals.change_given.currency),
    )
    
    use_case = CreateReceipt(receipt_repository)
    receipt = await use_case.execute(
        sale_id=request.sale_id,
        receipt_number=request.receipt_number,
        store_name=request.store_name,
        store_address=request.store_address,
        store_phone=request.store_phone,
        cashier_name=request.cashier_name,
        line_items=line_items,
        payments=payments,
        totals=totals,
        sale_date=request.sale_date,
        tax_rate=request.tax_rate,
        store_tax_id=request.store_tax_id,
        customer_name=request.customer_name,
        customer_email=request.customer_email,
        notes=request.notes,
        footer_message=request.footer_message,
        format_type=request.format_type,
        locale=request.locale,
    )
    
    return _receipt_to_response(receipt)


@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(
    receipt_id: str,
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
    receipt_repository: Annotated[ReceiptRepository, Depends(get_receipt_repository)],
) -> ReceiptResponse:
    """Get receipt by ID."""
    # Role check is performed by dependency injection above.

    use_case = GetReceipt(receipt_repository)
    try:
        receipt = await use_case.execute(receipt_id)
        return _receipt_to_response(receipt)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/sale/{sale_id}", response_model=ReceiptResponse)
async def get_receipt_by_sale_id(
    sale_id: str,
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
    receipt_repository: Annotated[ReceiptRepository, Depends(get_receipt_repository)],
) -> ReceiptResponse:
    """Get receipt by sale ID."""
    # Role check is performed by dependency injection above.

    use_case = GetReceiptBySaleId(receipt_repository)
    try:
        receipt = await use_case.execute(sale_id)
        return _receipt_to_response(receipt)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/number/{receipt_number}", response_model=ReceiptResponse)
async def get_receipt_by_number(
    receipt_number: str,
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
    receipt_repository: Annotated[ReceiptRepository, Depends(get_receipt_repository)],
) -> ReceiptResponse:
    """Get receipt by receipt number."""
    # Role check is performed by dependency injection above.

    use_case = GetReceiptByNumber(receipt_repository)
    try:
        receipt = await use_case.execute(receipt_number)
        return _receipt_to_response(receipt)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("", response_model=ReceiptListResponse)
async def list_receipts(
    start_date: str,
    end_date: str,
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
    receipt_repository: Annotated[ReceiptRepository, Depends(get_receipt_repository)],
    limit: int = 100,
    offset: int = 0,
) -> ReceiptListResponse:
    """List receipts by date range."""
    # Role check is performed by dependency injection above.

    use_case = ListReceiptsByDateRange(receipt_repository)
    receipts = await use_case.execute(start_date, end_date, limit, offset)
    
    return ReceiptListResponse(
        receipts=[_receipt_to_response(r) for r in receipts],
        total=len(receipts),
    )


@router.get("/{receipt_id}/pdf")
async def download_receipt_pdf(
    receipt_id: str,
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
    receipt_repository: Annotated[ReceiptRepository, Depends(get_receipt_repository)],
    pdf_generator: Annotated[ReceiptPDFGenerator, Depends(get_pdf_generator)],
) -> Response:
    """Download receipt as PDF."""
    # Role check is performed by dependency injection above.

    use_case = GetReceipt(receipt_repository)
    try:
        receipt = await use_case.execute(receipt_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    # Generate PDF
    pdf_bytes = pdf_generator.generate(receipt)
    
    # Return PDF response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=receipt_{receipt.receipt_number}.pdf"
        },
    )


@router.post("/{receipt_id}/email")
async def email_receipt(
    receipt_id: str,
    current_user: Annotated[User, Depends(require_roles(*SALES_ROLES))],
    receipt_repository: Annotated[ReceiptRepository, Depends(get_receipt_repository)],
    pdf_generator: Annotated[ReceiptPDFGenerator, Depends(get_pdf_generator)],
) -> dict:
    """Send receipt via email."""
    # Role check is performed by dependency injection above.

    use_case = GetReceipt(receipt_repository)
    try:
        receipt = await use_case.execute(receipt_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    if not receipt.customer_email:
        raise HTTPException(
            status_code=400,
            detail="Customer email is required to send receipt"
        )
    
    # Generate PDF
    pdf_bytes = pdf_generator.generate(receipt)
    
    # Send email asynchronously
    task = send_receipt_email.delay(
        to=receipt.customer_email,
        receipt_number=receipt.receipt_number,
        store_name=receipt.store_name,
        pdf_content=pdf_bytes,
    )
    
    return {
        "message": "Receipt email queued for delivery",
        "task_id": task.id,
        "email": receipt.customer_email,
    }


def _receipt_to_response(receipt: Receipt) -> ReceiptResponse:
    """Convert Receipt entity to response schema."""
    return ReceiptResponse(
        id=receipt.id,
        sale_id=receipt.sale_id,
        receipt_number=receipt.receipt_number,
        store_name=receipt.store_name,
        store_address=receipt.store_address,
        store_phone=receipt.store_phone,
        store_tax_id=receipt.store_tax_id,
        cashier_name=receipt.cashier_name,
        customer_name=receipt.customer_name,
        customer_email=receipt.customer_email,
        line_items=[
            ReceiptLineItemSchema(
                product_name=item.product_name,
                sku=item.sku,
                quantity=item.quantity,
                unit_price=MoneySchema(
                    amount=item.unit_price.amount,
                    currency=item.unit_price.currency,
                ),
                line_total=MoneySchema(
                    amount=item.line_total.amount,
                    currency=item.line_total.currency,
                ),
                discount_amount=MoneySchema(
                    amount=item.discount_amount.amount,
                    currency=item.discount_amount.currency,
                ),
            )
            for item in receipt.line_items
        ],
        payments=[
            ReceiptPaymentSchema(
                payment_method=payment.payment_method,
                amount=MoneySchema(
                    amount=payment.amount.amount,
                    currency=payment.amount.currency,
                ),
                reference_number=payment.reference_number,
                card_last_four=payment.card_last_four,
            )
            for payment in receipt.payments
        ],
        totals=ReceiptTotalsSchema(
            subtotal=MoneySchema(
                amount=receipt.totals.subtotal.amount,
                currency=receipt.totals.subtotal.currency,
            ),
            tax_amount=MoneySchema(
                amount=receipt.totals.tax_amount.amount,
                currency=receipt.totals.tax_amount.currency,
            ),
            discount_amount=MoneySchema(
                amount=receipt.totals.discount_amount.amount,
                currency=receipt.totals.discount_amount.currency,
            ),
            total=MoneySchema(
                amount=receipt.totals.total.amount,
                currency=receipt.totals.total.currency,
            ),
            amount_paid=MoneySchema(
                amount=receipt.totals.amount_paid.amount,
                currency=receipt.totals.amount_paid.currency,
            ),
            change_given=MoneySchema(
                amount=receipt.totals.change_given.amount,
                currency=receipt.totals.change_given.currency,
            ),
        ),
        sale_date=receipt.sale_date,
        tax_rate=receipt.tax_rate,
        notes=receipt.notes,
        footer_message=receipt.footer_message,
        format_type=receipt.format_type,
        locale=receipt.locale,
        created_at=receipt.created_at,
        version=receipt.version,
    )
