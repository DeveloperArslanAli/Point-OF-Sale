"""CSV report exporter with proper encoding and formatting."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.domain.reports.entities import ReportDefinition


class CSVReportExporter:
    """Export report data to CSV format with proper encoding."""

    DEFAULT_DELIMITER = ","
    DEFAULT_ENCODING = "utf-8-sig"  # UTF-8 with BOM for Excel compatibility

    def __init__(
        self,
        delimiter: str = DEFAULT_DELIMITER,
        encoding: str = DEFAULT_ENCODING,
    ):
        """
        Initialize exporter.
        
        Args:
            delimiter: CSV field delimiter
            encoding: Output encoding (utf-8-sig for Excel compatibility)
        """
        self.delimiter = delimiter
        self.encoding = encoding

    def export(
        self,
        data: list[dict[str, Any]],
        definition: ReportDefinition | None = None,
    ) -> bytes:
        """
        Export data to CSV format.
        
        Args:
            data: List of dictionaries containing report data
            definition: Optional report definition with column configuration
            
        Returns:
            CSV file as bytes
        """
        if not data:
            return b""

        output = io.StringIO()

        # Determine columns and headers
        if definition and definition.columns:
            columns = [c for c in definition.columns if c.visible]
            fields = [c.field for c in columns]
            headers = [c.label for c in columns]
        else:
            fields = list(data[0].keys())
            headers = [self._format_header(f) for f in fields]

        writer = csv.writer(
            output,
            delimiter=self.delimiter,
            quoting=csv.QUOTE_MINIMAL,
        )

        # Write header row
        writer.writerow(headers)

        # Write data rows
        for row in data:
            row_values = []
            for field in fields:
                value = row.get(field, "")
                row_values.append(self._format_value(value))
            writer.writerow(row_values)

        return output.getvalue().encode(self.encoding)

    def export_with_summary(
        self,
        data: list[dict[str, Any]],
        definition: ReportDefinition | None,
        summary: dict[str, Any],
    ) -> bytes:
        """
        Export data with summary section at the top.
        
        Args:
            data: Report data rows
            definition: Optional report definition
            summary: Summary statistics
            
        Returns:
            CSV file as bytes with summary section
        """
        output = io.StringIO()
        writer = csv.writer(
            output,
            delimiter=self.delimiter,
            quoting=csv.QUOTE_MINIMAL,
        )

        # Write summary section
        writer.writerow(["=== SUMMARY ==="])
        for key, value in summary.items():
            writer.writerow([self._format_header(key), self._format_value(value)])
        writer.writerow([])  # Blank row separator
        writer.writerow(["=== DETAIL DATA ==="])

        # Determine columns
        if definition and definition.columns:
            columns = [c for c in definition.columns if c.visible]
            fields = [c.field for c in columns]
            headers = [c.label for c in columns]
        elif data:
            fields = list(data[0].keys())
            headers = [self._format_header(f) for f in fields]
        else:
            return output.getvalue().encode(self.encoding)

        # Write headers and data
        writer.writerow(headers)
        for row in data:
            row_values = [self._format_value(row.get(field, "")) for field in fields]
            writer.writerow(row_values)

        return output.getvalue().encode(self.encoding)

    def _format_header(self, field: str) -> str:
        """Convert field name to header label."""
        return field.replace("_", " ").title()

    def _format_value(self, value: Any) -> str:
        """Format value for CSV output."""
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return str(float(value))
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (list, dict)):
            # For complex types, convert to JSON-like string
            import json
            return json.dumps(value)
        return str(value)


class TSVReportExporter(CSVReportExporter):
    """Export to tab-separated values format."""

    DEFAULT_DELIMITER = "\t"

    def __init__(self, encoding: str = CSVReportExporter.DEFAULT_ENCODING):
        """Initialize TSV exporter."""
        super().__init__(delimiter=self.DEFAULT_DELIMITER, encoding=encoding)
