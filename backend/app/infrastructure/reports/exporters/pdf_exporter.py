"""PDF report exporter using ReportLab."""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.domain.reports.entities import ReportDefinition


class PDFReportExporter:
    """Export report data to PDF format with professional formatting."""

    # Color scheme
    HEADER_BG = colors.HexColor("#4472C4")
    HEADER_TEXT = colors.white
    ALT_ROW_BG = colors.HexColor("#D9E2F3")
    BORDER_COLOR = colors.HexColor("#B4B4B4")
    
    # Page settings
    PAGE_SIZE = letter
    MARGIN = 0.75 * inch

    def __init__(self, page_size: tuple = None):
        """Initialize exporter with optional page size."""
        self.page_size = page_size or self.PAGE_SIZE
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=self.styles["Heading1"],
            fontSize=18,
            spaceAfter=20,
            textColor=colors.HexColor("#1F4E79"),
        ))
        self.styles.add(ParagraphStyle(
            name="ReportSubtitle",
            parent=self.styles["Normal"],
            fontSize=10,
            textColor=colors.gray,
            spaceAfter=15,
        ))
        self.styles.add(ParagraphStyle(
            name="SectionHeader",
            parent=self.styles["Heading2"],
            fontSize=12,
            spaceBefore=15,
            spaceAfter=10,
            textColor=colors.HexColor("#2E5A88"),
        ))

    def export(
        self,
        data: list[dict[str, Any]],
        definition: ReportDefinition,
        title: str | None = None,
    ) -> bytes:
        """
        Export data to PDF format.
        
        Args:
            data: List of dictionaries containing report data
            definition: Report definition with column configuration
            title: Optional report title
            
        Returns:
            PDF file as bytes
        """
        output = io.BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=self.page_size,
            leftMargin=self.MARGIN,
            rightMargin=self.MARGIN,
            topMargin=self.MARGIN,
            bottomMargin=self.MARGIN,
        )

        # Build document elements
        elements = []

        # Title
        report_title = title or definition.name
        elements.append(Paragraph(report_title, self.styles["ReportTitle"]))

        # Metadata
        meta_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total Rows: {len(data)}"
        elements.append(Paragraph(meta_text, self.styles["ReportSubtitle"]))

        # Determine columns
        if definition.columns:
            columns = [c for c in definition.columns if c.visible]
            fields = [c.field for c in columns]
            headers = [c.label for c in columns]
        else:
            fields = list(data[0].keys()) if data else []
            headers = [self._format_header(f) for f in fields]

        if not fields or not data:
            elements.append(Paragraph("No data available", self.styles["Normal"]))
            doc.build(elements)
            output.seek(0)
            return output.read()

        # Create data table
        table_data = [headers]  # Header row
        
        for row in data:
            row_values = []
            for field in fields:
                value = row.get(field, "")
                row_values.append(self._format_value(value))
            table_data.append(row_values)

        # Calculate column widths
        col_widths = self._calculate_column_widths(headers, table_data, fields)

        # Create table
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(self._get_table_style(len(data)))

        elements.append(table)

        # Build PDF
        doc.build(elements, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
        
        output.seek(0)
        return output.read()

    def export_with_summary(
        self,
        data: list[dict[str, Any]],
        definition: ReportDefinition,
        summary: dict[str, Any],
        title: str | None = None,
    ) -> bytes:
        """
        Export data with summary section.
        
        Args:
            data: Report data rows
            definition: Report definition
            summary: Summary statistics to display
            title: Optional report title
            
        Returns:
            PDF file as bytes
        """
        output = io.BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=self.page_size,
            leftMargin=self.MARGIN,
            rightMargin=self.MARGIN,
            topMargin=self.MARGIN,
            bottomMargin=self.MARGIN,
        )

        elements = []

        # Title
        report_title = title or definition.name
        elements.append(Paragraph(report_title, self.styles["ReportTitle"]))

        # Metadata
        meta_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        elements.append(Paragraph(meta_text, self.styles["ReportSubtitle"]))

        # Summary section
        elements.append(Paragraph("Summary", self.styles["SectionHeader"]))
        
        summary_data = [[self._format_header(k), self._format_value(v)] for k, v in summary.items()]
        summary_table = Table(summary_data, colWidths=[2.5 * inch, 2.5 * inch])
        summary_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, self.BORDER_COLOR),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        # Detail section
        elements.append(Paragraph("Detail Data", self.styles["SectionHeader"]))

        # Determine columns
        if definition.columns:
            columns = [c for c in definition.columns if c.visible]
            fields = [c.field for c in columns]
            headers = [c.label for c in columns]
        else:
            fields = list(data[0].keys()) if data else []
            headers = [self._format_header(f) for f in fields]

        if fields and data:
            table_data = [headers]
            for row in data:
                row_values = [self._format_value(row.get(field, "")) for field in fields]
                table_data.append(row_values)

            col_widths = self._calculate_column_widths(headers, table_data, fields)
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            table.setStyle(self._get_table_style(len(data)))
            elements.append(table)
        else:
            elements.append(Paragraph("No detail data available", self.styles["Normal"]))

        doc.build(elements, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
        
        output.seek(0)
        return output.read()

    def _format_header(self, field: str) -> str:
        """Convert field name to header label."""
        return field.replace("_", " ").title()

    def _format_value(self, value: Any) -> str:
        """Format value for display in PDF."""
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return f"${float(value):,.2f}" if float(value) >= 0 else f"-${abs(float(value)):,.2f}"
        if isinstance(value, float):
            if abs(value) >= 1000:
                return f"{value:,.2f}"
            return f"{value:.2f}"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (list, dict)):
            return str(value)[:50]  # Truncate long values
        return str(value)

    def _calculate_column_widths(
        self,
        headers: list[str],
        table_data: list[list[str]],
        fields: list[str],
    ) -> list[float]:
        """Calculate optimal column widths."""
        available_width = self.page_size[0] - (2 * self.MARGIN)
        num_cols = len(headers)
        
        # Calculate max width needed for each column
        max_widths = []
        for col_idx in range(num_cols):
            max_len = len(headers[col_idx])
            for row in table_data[:50]:  # Sample first 50 rows
                if col_idx < len(row):
                    max_len = max(max_len, len(str(row[col_idx])))
            max_widths.append(max_len)

        # Normalize to available width
        total_chars = sum(max_widths) or 1
        col_widths = [(w / total_chars) * available_width for w in max_widths]

        # Ensure minimum width
        min_width = 0.75 * inch
        col_widths = [max(w, min_width) for w in col_widths]

        # Scale if total exceeds available
        total_width = sum(col_widths)
        if total_width > available_width:
            scale = available_width / total_width
            col_widths = [w * scale for w in col_widths]

        return col_widths

    def _get_table_style(self, row_count: int) -> TableStyle:
        """Get table style with alternating row colors."""
        style_commands = [
            # Header styling
            ("BACKGROUND", (0, 0), (-1, 0), self.HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), self.HEADER_TEXT),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
            ("TOPPADDING", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            
            # Data styling
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 4),
            
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, self.BORDER_COLOR),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]

        # Add alternating row colors
        for row_idx in range(1, min(row_count + 1, 1000)):  # Limit for performance
            if row_idx % 2 == 0:
                style_commands.append(("BACKGROUND", (0, row_idx), (-1, row_idx), self.ALT_ROW_BG))

        return TableStyle(style_commands)

    def _add_page_number(self, canvas, doc) -> None:
        """Add page number footer to each page."""
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.gray)
        canvas.drawCentredString(
            self.page_size[0] / 2,
            0.5 * inch,
            text,
        )
        canvas.restoreState()


class PDFInvoiceExporter(PDFReportExporter):
    """Specialized exporter for invoice-style reports."""

    def export_invoice(
        self,
        header_info: dict[str, Any],
        line_items: list[dict[str, Any]],
        totals: dict[str, Any],
    ) -> bytes:
        """
        Export invoice-style PDF.
        
        Args:
            header_info: Invoice header (customer, date, number)
            line_items: Line item data
            totals: Summary totals (subtotal, tax, total)
            
        Returns:
            PDF file as bytes
        """
        output = io.BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=self.page_size,
            leftMargin=self.MARGIN,
            rightMargin=self.MARGIN,
            topMargin=self.MARGIN,
            bottomMargin=self.MARGIN,
        )

        elements = []

        # Header section
        elements.append(Paragraph("INVOICE", self.styles["ReportTitle"]))
        
        # Invoice details
        for key, value in header_info.items():
            elements.append(Paragraph(
                f"<b>{self._format_header(key)}:</b> {value}",
                self.styles["Normal"],
            ))
        elements.append(Spacer(1, 20))

        # Line items table
        headers = ["Item", "Description", "Qty", "Unit Price", "Total"]
        table_data = [headers]
        
        for item in line_items:
            table_data.append([
                item.get("name", ""),
                item.get("description", "")[:40],
                str(item.get("quantity", 0)),
                f"${item.get('unit_price', 0):,.2f}",
                f"${item.get('total', 0):,.2f}",
            ])

        table = Table(table_data, colWidths=[1.5*inch, 2.5*inch, 0.75*inch, 1*inch, 1*inch])
        table.setStyle(self._get_table_style(len(line_items)))
        elements.append(table)
        elements.append(Spacer(1, 20))

        # Totals section
        totals_data = [
            ["Subtotal:", f"${totals.get('subtotal', 0):,.2f}"],
            ["Tax:", f"${totals.get('tax', 0):,.2f}"],
            ["Total:", f"${totals.get('total', 0):,.2f}"],
        ]
        totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch])
        totals_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (0, -1), "RIGHT"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ]))
        elements.append(totals_table)

        doc.build(elements)
        
        output.seek(0)
        return output.read()
