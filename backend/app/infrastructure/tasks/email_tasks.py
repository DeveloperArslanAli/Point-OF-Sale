"""Celery tasks for email delivery."""
from __future__ import annotations

import smtplib
import structlog
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Any

from app.core.settings import get_settings
from app.infrastructure.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)
settings = get_settings()


@celery_app.task(bind=True, name="send_email", max_retries=3)
def send_email(
    self,
    to: str | list[str],
    subject: str,
    body: str,
    html: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """
    Send email via SMTP.
    
    Args:
        to: Recipient email(s)
        subject: Email subject
        body: Plain text body
        html: HTML body (optional)
        attachments: List of dicts with 'filename' and 'content' keys (content as bytes)
        
    Returns:
        Dict with status and message_id
    """
    logger.info("sending_email", to=to, subject=subject)
    
    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = getattr(settings, "SMTP_FROM_EMAIL", "noreply@retailpos.local")
        msg["To"] = to if isinstance(to, str) else ", ".join(to)
        
        # Add text/html parts
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if html:
            msg.attach(MIMEText(html, "html", "utf-8"))
        
        # Add attachments
        if attachments:
            for attachment in attachments:
                part = MIMEApplication(attachment["content"])
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=attachment["filename"]
                )
                msg.attach(part)
        
        # Send via SMTP (if configured)
        smtp_host = getattr(settings, "SMTP_HOST", None)
        smtp_port = getattr(settings, "SMTP_PORT", 587)
        smtp_user = getattr(settings, "SMTP_USER", None)
        smtp_password = getattr(settings, "SMTP_PASSWORD", None)
        
        if not smtp_host:
            # Development mode - just log
            logger.warning("smtp_not_configured", message="Email would be sent in production")
            return {
                "status": "simulated",
                "message_id": f"dev-{hash(subject)}",
            }
        
        # Production mode - send via SMTP
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_user and smtp_password:
                server.starttls()
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        logger.info("email_sent", to=to, subject=subject)
        return {
            "status": "sent",
            "message_id": msg["Message-ID"] or f"sent-{hash(subject)}",
        }
        
    except Exception as exc:
        logger.error("email_send_failed", to=to, subject=subject, error=str(exc))
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="send_report_email")
def send_report_email(
    to: str | list[str],
    report_type: str,
    report_data: dict[str, Any],
) -> dict[str, str]:
    """
    Send a formatted report via email.
    
    Args:
        to: Recipient email(s)
        report_type: Type of report (e.g., 'sales', 'inventory')
        report_data: Report data dict
        
    Returns:
        Dict with send status
    """
    logger.info("sending_report_email", to=to, report_type=report_type)
    
    # Format report as HTML
    if report_type == "sales":
        subject = f"Sales Report: {report_data['period']['start']} to {report_data['period']['end']}"
        html_body = _format_sales_report_html(report_data)
    elif report_type == "inventory":
        subject = f"Inventory Report: {report_data['generated_at']}"
        html_body = _format_inventory_report_html(report_data)
    else:
        subject = f"Report: {report_type}"
        html_body = f"<pre>{report_data}</pre>"
    
    # Plain text fallback
    text_body = f"Report Type: {report_type}\nSee HTML version for formatted report."
    
    return send_email(to, subject, text_body, html_body)


def _format_sales_report_html(data: dict[str, Any]) -> str:
    """Format sales report as HTML."""
    summary = data["summary"]
    top_products = data["top_products"]
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #4CAF50; color: white; }}
            .metric {{ font-size: 24px; font-weight: bold; color: #4CAF50; }}
        </style>
    </head>
    <body>
        <h1>Sales Report</h1>
        <p><strong>Period:</strong> {data['period']['start']} to {data['period']['end']}</p>
        
        <h2>Summary</h2>
        <p>Total Sales: <span class="metric">{summary['total_sales']}</span></p>
        <p>Total Revenue: <span class="metric">${summary['total_revenue']:,.2f}</span></p>
        <p>Average Sale: <span class="metric">${summary['avg_sale_amount']:,.2f}</span></p>
        
        <h2>Top 10 Products</h2>
        <table>
            <tr>
                <th>Product</th>
                <th>SKU</th>
                <th>Quantity Sold</th>
                <th>Revenue</th>
            </tr>
    """
    
    for product in top_products:
        html += f"""
            <tr>
                <td>{product['name']}</td>
                <td>{product['sku']}</td>
                <td>{product['quantity']}</td>
                <td>${product['revenue']:,.2f}</td>
            </tr>
        """
    
    html += """
        </table>
    </body>
    </html>
    """
    return html


def _format_inventory_report_html(data: dict[str, Any]) -> str:
    """Format inventory report as HTML."""
    summary = data["summary"]
    
    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .metric {{ font-size: 24px; font-weight: bold; color: #2196F3; }}
        </style>
    </head>
    <body>
        <h1>Inventory Report</h1>
        <p><strong>Generated:</strong> {data['generated_at']}</p>
        
        <h2>Summary</h2>
        <p>Total Products: <span class="metric">{summary['total_products']}</span></p>
        <p>Active Products: <span class="metric">{summary['active_products']}</span></p>
        <p>Inactive Products: <span class="metric">{summary['inactive_products']}</span></p>
    </body>
    </html>
    """


@celery_app.task(name="send_import_notification")
def send_import_notification(
    to: str,
    job_id: str,
    filename: str,
    status: str,
    processed: int,
    failed: int,
) -> dict[str, str]:
    """
    Send product import completion notification.
    
    Args:
        to: Recipient email
        job_id: Import job ID
        filename: Original filename
        status: Job status
        processed: Number of successful imports
        failed: Number of failed imports
        
    Returns:
        Dict with send status
    """
    subject = f"Product Import Complete: {filename}"
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .success {{ color: #4CAF50; }}
            .error {{ color: #f44336; }}
        </style>
    </head>
    <body>
        <h1>Product Import Complete</h1>
        <p><strong>File:</strong> {filename}</p>
        <p><strong>Job ID:</strong> {job_id}</p>
        <p><strong>Status:</strong> <span class="{'success' if status == 'completed' else 'error'}">{status}</span></p>
        
        <h2>Results</h2>
        <p><span class="success">Successfully Imported: {processed}</span></p>
        <p><span class="error">Failed: {failed}</span></p>
    </body>
    </html>
    """
    
    text = f"""
Product Import Complete

File: {filename}
Job ID: {job_id}
Status: {status}

Results:
- Successfully Imported: {processed}
- Failed: {failed}
    """
    
    return send_email(to, subject, text, html)


@celery_app.task(name="send_receipt_email")
def send_receipt_email(
    to: str,
    receipt_number: str,
    store_name: str,
    pdf_content: bytes,
) -> dict[str, str]:
    """
    Send receipt PDF via email.
    
    Args:
        to: Recipient email
        receipt_number: Receipt number
        store_name: Store name
        pdf_content: PDF file content as bytes
        
    Returns:
        Dict with send status
    """
    logger.info("sending_receipt_email", to=to, receipt_number=receipt_number)
    
    subject = f"Receipt {receipt_number} from {store_name}"
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{store_name}</h1>
            <p>Thank you for your purchase!</p>
        </div>
        
        <p>Dear Customer,</p>
        
        <p>Thank you for shopping with us. Please find your receipt attached to this email.</p>
        
        <p><strong>Receipt Number:</strong> {receipt_number}</p>
        
        <p>If you have any questions about this purchase, please don't hesitate to contact us.</p>
        
        <p>Best regards,<br>
        {store_name}</p>
    </body>
    </html>
    """
    
    text = f"""
{store_name}

Thank you for your purchase!

Dear Customer,

Thank you for shopping with us. Please find your receipt attached to this email.

Receipt Number: {receipt_number}

If you have any questions about this purchase, please don't hesitate to contact us.

Best regards,
{store_name}
    """
    
    # Attach PDF
    attachments = [
        {
            "filename": f"receipt_{receipt_number}.pdf",
            "content": pdf_content,
        }
    ]
    
    return send_email(to, subject, text, html, attachments)

