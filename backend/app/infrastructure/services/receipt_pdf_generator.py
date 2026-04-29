"""Receipt PDF generation service using ReportLab."""

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Optional
from urllib.request import urlopen

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from app.domain.receipts import Receipt


def hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert hex color to RGB tuple (0-1 range)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join([c * 2 for c in hex_color])
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    return (r, g, b)


class ReceiptPDFGenerator:
    """Generate PDF receipts in thermal or A4 format with branding support."""

    # Thermal receipt dimensions (80mm width)
    THERMAL_WIDTH = 80 * mm
    THERMAL_MARGIN = 5 * mm

    # A4 receipt dimensions
    A4_WIDTH, A4_HEIGHT = A4
    A4_MARGIN = 20 * mm

    def __init__(self) -> None:
        """Initialize PDF generator."""
        self.styles = getSampleStyleSheet()

    def generate(self, receipt: Receipt) -> bytes:
        """Generate PDF receipt."""
        if receipt.format_type == "thermal":
            return self._generate_thermal(receipt)
        elif receipt.format_type == "a4":
            return self._generate_a4(receipt)
        else:
            raise ValueError(f"Unsupported format type: {receipt.format_type}")

    def _get_primary_color(self, receipt: Receipt) -> tuple[float, float, float]:
        """Get primary color from branding or default."""
        if receipt.branding and receipt.branding.primary_color:
            return hex_to_rgb(receipt.branding.primary_color)
        return (0.1, 0.46, 0.82)  # Default blue

    def _get_secondary_color(self, receipt: Receipt) -> tuple[float, float, float]:
        """Get secondary color from branding or default."""
        if receipt.branding and receipt.branding.secondary_color:
            return hex_to_rgb(receipt.branding.secondary_color)
        return (0.26, 0.26, 0.26)  # Default dark gray

    def _format_amount(self, receipt: Receipt, amount: Decimal) -> str:
        """Format amount using receipt's currency configuration."""
        return receipt.format_amount(amount)

    def _draw_logo(self, c: canvas.Canvas, receipt: Receipt, x: float, y: float, max_width: float = 50, max_height: float = 30) -> float:
        """Draw logo if available and configured. Returns height used."""
        if not receipt.branding or not receipt.branding.logo_url or not receipt.branding.show_logo_on_receipt:
            return 0
        
        try:
            # Try to load image from URL
            img = ImageReader(receipt.branding.logo_url)
            iw, ih = img.getSize()
            aspect = ih / iw
            
            # Scale to fit
            w = min(max_width * mm, iw)
            h = w * aspect
            if h > max_height * mm:
                h = max_height * mm
                w = h / aspect
            
            c.drawImage(img, x - w / 2, y - h, width=w, height=h, preserveAspectRatio=True, mask="auto")
            return h + 5 * mm
        except Exception:
            # If logo fails to load, skip it
            return 0

    def _generate_thermal(self, receipt: Receipt) -> bytes:
        """Generate thermal receipt (80mm width)."""
        buffer = BytesIO()
        
        # Calculate height dynamically based on content
        estimated_height = self._estimate_thermal_height(receipt)
        
        c = canvas.Canvas(buffer, pagesize=(self.THERMAL_WIDTH, estimated_height))
        
        y_position = estimated_height - self.THERMAL_MARGIN
        x_center = self.THERMAL_WIDTH / 2
        x_left = self.THERMAL_MARGIN
        
        # Get branding colors
        primary_color = self._get_primary_color(receipt)
        
        # Draw logo if available
        logo_height = self._draw_logo(c, receipt, x_center, y_position, max_width=40, max_height=20)
        y_position -= logo_height
        
        # Store header (use branding company name if available)
        store_name = receipt.store_name
        if receipt.branding and receipt.branding.company_name:
            store_name = receipt.branding.company_name
        
        c.setFillColorRGB(*primary_color)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(x_center, y_position, store_name)
        y_position -= 16
        
        # Tagline if available
        if receipt.branding and receipt.branding.tagline:
            c.setFillColorRGB(0.5, 0.5, 0.5)
            c.setFont("Helvetica-Oblique", 7)
            c.drawCentredString(x_center, y_position, receipt.branding.tagline)
            y_position -= 10
        
        c.setFillColorRGB(0, 0, 0)  # Reset to black
        c.setFont("Helvetica", 8)
        for line in receipt.store_address.split("\n"):
            c.drawCentredString(x_center, y_position, line.strip())
            y_position -= 10
        
        c.drawCentredString(x_center, y_position, receipt.store_phone)
        y_position -= 10
        
        if receipt.store_tax_id:
            c.drawCentredString(x_center, y_position, f"Tax ID: {receipt.store_tax_id}")
            y_position -= 10
        
        # Separator with primary color
        y_position -= 5
        c.setStrokeColorRGB(*primary_color)
        c.line(x_left, y_position, self.THERMAL_WIDTH - self.THERMAL_MARGIN, y_position)
        c.setStrokeColorRGB(0, 0, 0)  # Reset
        y_position -= 10
        
        # Receipt info
        c.setFont("Helvetica", 8)
        receipt_label = "Invoice" if receipt.invoice_prefix else "Receipt"
        c.drawString(x_left, y_position, f"{receipt_label}: {receipt.receipt_number}")
        y_position -= 10
        c.drawString(x_left, y_position, f"Date: {receipt.sale_date.strftime('%Y-%m-%d %H:%M:%S')}")
        y_position -= 10
        c.drawString(x_left, y_position, f"Cashier: {receipt.cashier_name}")
        y_position -= 10
        
        if receipt.customer_name:
            c.drawString(x_left, y_position, f"Customer: {receipt.customer_name}")
            y_position -= 10
        
        # Separator
        y_position -= 5
        c.line(x_left, y_position, self.THERMAL_WIDTH - self.THERMAL_MARGIN, y_position)
        y_position -= 10
        
        # Line items
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x_left, y_position, "Items")
        y_position -= 12
        
        c.setFont("Helvetica", 7)
        for item in receipt.line_items:
            # Product name
            c.drawString(x_left, y_position, item.product_name[:30])
            y_position -= 9
            
            # Quantity, price, total - using formatted amounts
            qty_text = f"{item.quantity} x {self._format_amount(receipt, item.unit_price.amount)}"
            total_text = self._format_amount(receipt, item.line_total.amount)
            c.drawString(x_left + 5, y_position, qty_text)
            c.drawRightString(self.THERMAL_WIDTH - self.THERMAL_MARGIN, y_position, total_text)
            y_position -= 9
            
            if item.discount_amount.amount > 0:
                c.drawString(x_left + 5, y_position, "Discount")
                c.drawRightString(
                    self.THERMAL_WIDTH - self.THERMAL_MARGIN,
                    y_position,
                    f"-{self._format_amount(receipt, item.discount_amount.amount)}"
                )
                y_position -= 9
            
            y_position -= 3  # Extra spacing between items
        
        # Separator
        y_position -= 5
        c.line(x_left, y_position, self.THERMAL_WIDTH - self.THERMAL_MARGIN, y_position)
        y_position -= 10
        
        # Totals with formatted amounts
        c.setFont("Helvetica", 8)
        totals_data = [
            ("Subtotal:", self._format_amount(receipt, receipt.totals.subtotal.amount)),
        ]
        
        if receipt.totals.discount_amount.amount > 0:
            totals_data.append(("Discount:", f"-{self._format_amount(receipt, receipt.totals.discount_amount.amount)}"))
        
        totals_data.extend([
            (f"Tax ({receipt.tax_rate}%):", self._format_amount(receipt, receipt.totals.tax_amount.amount)),
        ])
        
        for label, value in totals_data:
            c.drawString(x_left, y_position, label)
            c.drawRightString(self.THERMAL_WIDTH - self.THERMAL_MARGIN, y_position, value)
            y_position -= 10
        
        # Total with primary color
        y_position -= 3
        c.setFillColorRGB(*primary_color)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x_left, y_position, "TOTAL:")
        c.drawRightString(
            self.THERMAL_WIDTH - self.THERMAL_MARGIN,
            y_position,
            self._format_amount(receipt, receipt.totals.total.amount)
        )
        c.setFillColorRGB(0, 0, 0)  # Reset to black
        y_position -= 15
        
        # Payments
        c.setFont("Helvetica", 8)
        for payment in receipt.payments:
            payment_label = payment.payment_method.upper()
            if payment.card_last_four:
                payment_label += f" (****{payment.card_last_four})"
            c.drawString(x_left, y_position, payment_label)
            c.drawRightString(
                self.THERMAL_WIDTH - self.THERMAL_MARGIN,
                y_position,
                self._format_amount(receipt, payment.amount.amount)
            )
            y_position -= 10
        
        if receipt.totals.change_given.amount > 0:
            c.drawString(x_left, y_position, "Change:")
            c.drawRightString(
                self.THERMAL_WIDTH - self.THERMAL_MARGIN,
                y_position,
                self._format_amount(receipt, receipt.totals.change_given.amount)
            )
            y_position -= 10
        
        # Footer
        if receipt.notes:
            y_position -= 10
            c.setFont("Helvetica-Oblique", 7)
            c.drawCentredString(x_center, y_position, receipt.notes)
            y_position -= 10
        
        if receipt.footer_message:
            y_position -= 10
            c.setFillColorRGB(*primary_color)
            c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(x_center, y_position, receipt.footer_message)
            c.setFillColorRGB(0, 0, 0)
        
        c.save()
        buffer.seek(0)
        return buffer.read()

    def _generate_a4(self, receipt: Receipt) -> bytes:
        """Generate A4 format receipt with branding support."""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        
        y_position = self.A4_HEIGHT - self.A4_MARGIN
        x_left = self.A4_MARGIN
        x_right = self.A4_WIDTH - self.A4_MARGIN
        x_center = self.A4_WIDTH / 2
        
        # Get branding colors
        primary_color = self._get_primary_color(receipt)
        
        # Draw logo if available
        logo_height = self._draw_logo(c, receipt, x_center, y_position, max_width=80, max_height=40)
        y_position -= logo_height
        
        # Store header (use branding company name if available)
        store_name = receipt.store_name
        if receipt.branding and receipt.branding.company_name:
            store_name = receipt.branding.company_name
        
        c.setFillColorRGB(*primary_color)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(x_center, y_position, store_name)
        y_position -= 25
        
        # Tagline if available
        if receipt.branding and receipt.branding.tagline:
            c.setFillColorRGB(0.5, 0.5, 0.5)
            c.setFont("Helvetica-Oblique", 10)
            c.drawCentredString(x_center, y_position, receipt.branding.tagline)
            y_position -= 16
        
        c.setFillColorRGB(0, 0, 0)  # Reset to black
        c.setFont("Helvetica", 10)
        for line in receipt.store_address.split("\n"):
            c.drawCentredString(x_center, y_position, line.strip())
            y_position -= 14
        
        c.drawCentredString(x_center, y_position, receipt.store_phone)
        y_position -= 14
        
        if receipt.store_tax_id:
            c.drawCentredString(x_center, y_position, f"Tax ID: {receipt.store_tax_id}")
            y_position -= 14
        
        # Separator with primary color
        y_position -= 20
        c.setStrokeColorRGB(*primary_color)
        c.setLineWidth(2)
        c.line(x_left, y_position, x_right, y_position)
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(1)
        y_position -= 20
        
        # Receipt info (two columns)
        receipt_label = "Invoice" if receipt.invoice_prefix else "Receipt"
        c.setFont("Helvetica", 10)
        c.drawString(x_left, y_position, f"{receipt_label} #: {receipt.receipt_number}")
        c.drawRightString(x_right, y_position, f"Date: {receipt.sale_date.strftime('%Y-%m-%d %H:%M:%S')}")
        y_position -= 14
        
        c.drawString(x_left, y_position, f"Cashier: {receipt.cashier_name}")
        if receipt.customer_name:
            c.drawRightString(x_right, y_position, f"Customer: {receipt.customer_name}")
        y_position -= 20
        
        # Line items table header
        c.line(x_left, y_position, x_right, y_position)
        y_position -= 15
        
        c.setFillColorRGB(*primary_color)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x_left, y_position, "Item")
        c.drawString(x_left + 250, y_position, "Qty")
        c.drawString(x_left + 300, y_position, "Price")
        c.drawString(x_left + 370, y_position, "Discount")
        c.drawRightString(x_right, y_position, "Total")
        c.setFillColorRGB(0, 0, 0)
        y_position -= 5
        
        c.line(x_left, y_position, x_right, y_position)
        y_position -= 15
        
        c.setFont("Helvetica", 9)
        for item in receipt.line_items:
            c.drawString(x_left, y_position, item.product_name[:35])
            c.drawString(x_left + 250, y_position, str(item.quantity))
            c.drawString(x_left + 300, y_position, self._format_amount(receipt, item.unit_price.amount))
            
            if item.discount_amount.amount > 0:
                c.drawString(x_left + 370, y_position, f"-{self._format_amount(receipt, item.discount_amount.amount)}")
            else:
                c.drawString(x_left + 370, y_position, "-")
            
            c.drawRightString(x_right, y_position, self._format_amount(receipt, item.line_total.amount))
            y_position -= 14
        
        # Separator
        y_position -= 5
        c.line(x_left, y_position, x_right, y_position)
        y_position -= 20
        
        # Totals (right-aligned)
        c.setFont("Helvetica", 10)
        totals_x = x_right - 150
        
        c.drawString(totals_x, y_position, "Subtotal:")
        c.drawRightString(x_right, y_position, self._format_amount(receipt, receipt.totals.subtotal.amount))
        y_position -= 14
        
        if receipt.totals.discount_amount.amount > 0:
            c.drawString(totals_x, y_position, "Discount:")
            c.drawRightString(x_right, y_position, f"-{self._format_amount(receipt, receipt.totals.discount_amount.amount)}")
            y_position -= 14
        
        c.drawString(totals_x, y_position, f"Tax ({receipt.tax_rate}%):")
        c.drawRightString(x_right, y_position, self._format_amount(receipt, receipt.totals.tax_amount.amount))
        y_position -= 20
        
        # Total with primary color highlight
        c.setFillColorRGB(*primary_color)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(totals_x, y_position, "TOTAL:")
        c.drawRightString(x_right, y_position, self._format_amount(receipt, receipt.totals.total.amount))
        c.setFillColorRGB(0, 0, 0)
        y_position -= 25
        
        # Payments
        c.setFont("Helvetica", 10)
        for payment in receipt.payments:
            payment_label = payment.payment_method.upper()
            if payment.card_last_four:
                payment_label += f" (****{payment.card_last_four})"
            c.drawString(totals_x, y_position, payment_label)
            c.drawRightString(x_right, y_position, self._format_amount(receipt, payment.amount.amount))
            y_position -= 14
        
        if receipt.totals.change_given.amount > 0:
            c.drawString(totals_x, y_position, "Change:")
            c.drawRightString(x_right, y_position, self._format_amount(receipt, receipt.totals.change_given.amount))
            y_position -= 14
        
        # Footer
        if receipt.notes:
            y_position -= 30
            c.setFont("Helvetica-Oblique", 9)
            c.drawCentredString(x_center, y_position, receipt.notes)
        
        if receipt.footer_message:
            y_position -= 40
            c.setFillColorRGB(*primary_color)
            c.setFont("Helvetica-Bold", 11)
            c.drawCentredString(x_center, y_position, receipt.footer_message)
            c.setFillColorRGB(0, 0, 0)
        
        c.save()
        buffer.seek(0)
        return buffer.read()

    def _estimate_thermal_height(self, receipt: Receipt) -> float:
        """Estimate thermal receipt height based on content."""
        base_height = 100 * mm  # Base height for header and footer
        
        # Add extra for branding (logo + tagline)
        if receipt.branding:
            if receipt.branding.logo_url and receipt.branding.show_logo_on_receipt:
                base_height += 25 * mm
            if receipt.branding.tagline:
                base_height += 10 * mm
        
        # Line items (approximately 20mm per item with discount)
        items_height = len(receipt.line_items) * 20 * mm
        
        # Totals section
        totals_height = 50 * mm
        
        # Payments
        payments_height = len(receipt.payments) * 10 * mm
        
        # Extra for notes
        notes_height = 20 * mm if receipt.notes else 0
        
        return base_height + items_height + totals_height + payments_height + notes_height
