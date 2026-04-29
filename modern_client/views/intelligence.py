"""Inventory Intelligence View for Desktop Client.

Displays:
- Low stock alerts
- Dead stock items
- ABC classification
- Purchase suggestions
- Demand forecasting with exponential smoothing controls
"""

import flet as ft
from decimal import Decimal
from services.api import api_service

icons = ft.icons


class IntelligenceView(ft.Container):
    """Inventory Intelligence dashboard view."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 20

        # Data holders
        self.insights_data = None
        self.abc_data = None
        self.forecast_data = None
        self.suggestions_data = None
        self.vendor_data = None
        self.po_drafts_data = None

        # Tab selection
        self.selected_tab = 0
        
        # Forecast parameters
        self.smoothing_alpha = 0.3
        self.seasonality_enabled = True

        # Build UI
        self.content = self._build_layout()
        self._load_data()

    def _safe_float(self, value, default: float = 0.0) -> float:
        """Coerce numbers that may come back as strings to float safely."""
        try:
            return float(value)
        except (TypeError, ValueError):
            try:
                return float(Decimal(str(value)))
            except (TypeError, ValueError, ArithmeticError):
                return default

    def _build_layout(self):
        """Build the main layout with tabs."""
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            on_change=self._on_tab_change,
            tabs=[
                ft.Tab(text="Overview", icon=icons.DASHBOARD),
                ft.Tab(text="Low Stock", icon=icons.WARNING),
                ft.Tab(text="Dead Stock", icon=icons.DELETE_FOREVER),
                ft.Tab(text="ABC Analysis", icon=icons.ANALYTICS),
                ft.Tab(text="Forecasts", icon=icons.TRENDING_UP),
                ft.Tab(text="PO Suggestions", icon=icons.SHOPPING_CART),
                ft.Tab(text="Vendor Scorecard", icon=icons.BUSINESS),
                ft.Tab(text="PO Drafts", icon=icons.DOCUMENT_SCANNER),
            ],
        )

        self.content_area = ft.Container(
            content=self._build_loading(),
            expand=True,
            bgcolor="#1a1c1e",
            border_radius=10,
            padding=20,
        )

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Inventory Intelligence", size=28, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            "Refresh",
                            icon=icons.REFRESH,
                            bgcolor="#bb86fc",
                            color="black",
                            on_click=self._refresh_data,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(height=10),
                self.tabs,
                ft.Container(height=10),
                self.content_area,
            ],
            expand=True,
        )

    def _build_loading(self):
        """Build loading indicator."""
        return ft.Column(
            [
                ft.ProgressRing(color="#bb86fc"),
                ft.Text("Loading intelligence data...", color="grey"),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

    def _on_tab_change(self, e):
        """Handle tab change."""
        self.selected_tab = e.control.selected_index
        self._render_tab_content()

    def _refresh_data(self, e=None):
        """Refresh all intelligence data."""
        self.content_area.content = self._build_loading()
        if self.page:
            self.page.update()
        self._load_data()

    def _load_data(self):
        """Load all intelligence data from API."""
        try:
            self.insights_data = api_service.get_inventory_insights()
            self.abc_data = api_service.get_inventory_abc()
            self.forecast_data = api_service.get_inventory_forecast()
            self.suggestions_data = api_service.get_purchase_suggestions()
            self.vendor_data = api_service.get_vendor_performance()
            self.po_drafts_data = api_service.get_po_drafts()
        except Exception as e:
            print(f"Error loading intelligence data: {e}")

        self._render_tab_content()

    def _render_tab_content(self):
        """Render content based on selected tab."""
        if self.selected_tab == 0:
            content = self._build_overview()
        elif self.selected_tab == 1:
            content = self._build_low_stock()
        elif self.selected_tab == 2:
            content = self._build_dead_stock()
        elif self.selected_tab == 3:
            content = self._build_abc_analysis()
        elif self.selected_tab == 4:
            content = self._build_forecasts()
        elif self.selected_tab == 5:
            content = self._build_po_suggestions()
        elif self.selected_tab == 6:
            content = self._build_vendor_scorecard()
        elif self.selected_tab == 7:
            content = self._build_po_drafts()
        else:
            content = ft.Text("Unknown tab", color="white")

        self.content_area.content = content
        if self.page:
            self.page.update()

    def _build_overview(self):
        """Build overview dashboard with key metrics."""
        low_stock_count = len(self.insights_data.get("low_stock", [])) if self.insights_data else 0
        dead_stock_count = len(self.insights_data.get("dead_stock", [])) if self.insights_data else 0
        forecast_count = len(self.forecast_data.get("forecasts", [])) if self.forecast_data else 0
        suggestions_count = len(self.suggestions_data.get("suggestions", [])) if self.suggestions_data else 0

        # Count ABC categories
        a_count = b_count = c_count = 0
        if self.abc_data:
            for item in self.abc_data.get("classifications", []):
                if item.get("abc_class") == "A":
                    a_count += 1
                elif item.get("abc_class") == "B":
                    b_count += 1
                elif item.get("abc_class") == "C":
                    c_count += 1

        return ft.Column(
            [
                ft.Text("Intelligence Overview", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=20),
                ft.Row(
                    [
                        self._build_metric_card("Low Stock Items", str(low_stock_count), icons.WARNING, "#ff9800"),
                        self._build_metric_card("Dead Stock Items", str(dead_stock_count), icons.DELETE_FOREVER, "#f44336"),
                        self._build_metric_card("Products Forecasted", str(forecast_count), icons.TRENDING_UP, "#4caf50"),
                        self._build_metric_card("PO Suggestions", str(suggestions_count), icons.SHOPPING_CART, "#2196f3"),
                    ],
                    wrap=True,
                    spacing=20,
                ),
                ft.Container(height=30),
                ft.Text("ABC Classification Summary", size=18, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                ft.Row(
                    [
                        self._build_abc_summary_card("A", a_count, "High Value (70%)", "#4caf50"),
                        self._build_abc_summary_card("B", b_count, "Medium Value (20%)", "#ff9800"),
                        self._build_abc_summary_card("C", c_count, "Low Value (10%)", "#9e9e9e"),
                    ],
                    wrap=True,
                    spacing=20,
                ),
                ft.Container(height=30),
                self._build_data_freshness(),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _build_metric_card(self, title, value, icon, color):
        """Build a metric card."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, color=color, size=30),
                            ft.Text(value, size=28, weight=ft.FontWeight.BOLD, color="white"),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(title, color="grey", size=14),
                ],
            ),
            width=200,
            padding=20,
            bgcolor="#2d3033",
            border_radius=10,
        )

    def _build_abc_summary_card(self, category, count, description, color):
        """Build ABC category summary card."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Text(category, size=24, weight=ft.FontWeight.BOLD, color="white"),
                        width=50,
                        height=50,
                        bgcolor=color,
                        border_radius=25,
                        alignment=ft.alignment.center,
                    ),
                    ft.Text(f"{count} Products", size=16, color="white"),
                    ft.Text(description, size=12, color="grey"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=20,
            bgcolor="#2d3033",
            border_radius=10,
            width=180,
        )

    def _build_data_freshness(self):
        """Build data freshness indicator."""
        generated_at = "N/A"
        is_stale = False

        if self.forecast_data:
            generated_at = self.forecast_data.get("generated_at", "N/A")
            is_stale = self.forecast_data.get("stale", False)

        color = "#f44336" if is_stale else "#4caf50"
        status = "STALE - Refresh recommended" if is_stale else "Fresh"

        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icons.ACCESS_TIME, color=color),
                    ft.Text(f"Data generated: {generated_at[:19] if len(generated_at) > 19 else generated_at}", color="grey"),
                    ft.Text(f"Status: {status}", color=color),
                ],
                spacing=20,
            ),
            padding=15,
            bgcolor="#2d3033",
            border_radius=10,
        )

    def _build_low_stock(self):
        """Build low stock items table."""
        items = self.insights_data.get("low_stock", []) if self.insights_data else []

        if not items:
            return ft.Column(
                [
                    ft.Icon(icons.CHECK_CIRCLE, color="#4caf50", size=60),
                    ft.Text("No low stock items!", size=18, color="white"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )

        rows = []
        for item in items:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item.get("name", ""), color="white")),
                        ft.DataCell(ft.Text(item.get("sku", ""), color="grey")),
                        ft.DataCell(ft.Text(str(item.get("quantity_on_hand", 0)), color="#f44336")),
                        ft.DataCell(ft.Text(str(item.get("reorder_point", 0)), color="#ff9800")),
                        ft.DataCell(ft.Text(str(item.get("recommended_order", 0)), color="#4caf50")),
                        ft.DataCell(ft.Text(f"{item.get('daily_demand', 0)}/day", color="grey")),
                    ]
                )
            )

        return ft.Column(
            [
                ft.Text(f"Low Stock Items ({len(items)})", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Product")),
                        ft.DataColumn(ft.Text("SKU")),
                        ft.DataColumn(ft.Text("On Hand")),
                        ft.DataColumn(ft.Text("Reorder Point")),
                        ft.DataColumn(ft.Text("Recommended Order")),
                        ft.DataColumn(ft.Text("Daily Demand")),
                    ],
                    rows=rows,
                    heading_row_color="#2d3033",
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _build_dead_stock(self):
        """Build dead stock items table."""
        items = self.insights_data.get("dead_stock", []) if self.insights_data else []

        if not items:
            return ft.Column(
                [
                    ft.Icon(icons.CHECK_CIRCLE, color="#4caf50", size=60),
                    ft.Text("No dead stock items!", size=18, color="white"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )

        rows = []
        for item in items:
            days = item.get("days_since_movement", 0)
            color = "#f44336" if days > 180 else "#ff9800"
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item.get("name", ""), color="white")),
                        ft.DataCell(ft.Text(item.get("sku", ""), color="grey")),
                        ft.DataCell(ft.Text(str(item.get("quantity_on_hand", 0)), color="grey")),
                        ft.DataCell(ft.Text(f"{days} days", color=color)),
                    ]
                )
            )

        return ft.Column(
            [
                ft.Text(f"Dead Stock Items ({len(items)})", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Text("Products with no movement in 90+ days", size=14, color="grey"),
                ft.Container(height=10),
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Product")),
                        ft.DataColumn(ft.Text("SKU")),
                        ft.DataColumn(ft.Text("On Hand")),
                        ft.DataColumn(ft.Text("Days Since Movement")),
                    ],
                    rows=rows,
                    heading_row_color="#2d3033",
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _build_abc_analysis(self):
        """Build ABC classification table."""
        items = self.abc_data.get("classifications", []) if self.abc_data else []

        if not items:
            return ft.Text("No ABC data available", color="grey")

        rows = []
        for item in items:
            abc_class = item.get("abc_class", "C")
            color = {"A": "#4caf50", "B": "#ff9800", "C": "#9e9e9e"}.get(abc_class, "#9e9e9e")

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(abc_class, color="white", weight=ft.FontWeight.BOLD),
                                width=30,
                                height=30,
                                bgcolor=color,
                                border_radius=15,
                                alignment=ft.alignment.center,
                            )
                        ),
                        ft.DataCell(ft.Text(item.get("name", ""), color="white")),
                        ft.DataCell(ft.Text(item.get("sku", ""), color="grey")),
                        ft.DataCell(ft.Text(str(item.get("usage_quantity", 0)), color="white")),
                        ft.DataCell(ft.Text(f"${item.get('usage_value', 0)}", color="#bb86fc")),
                        ft.DataCell(ft.Text(f"{item.get('cumulative_percent', 0)}%", color="grey")),
                    ]
                )
            )

        return ft.Column(
            [
                ft.Text("ABC Classification", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Text("Products ranked by value contribution", size=14, color="grey"),
                ft.Container(height=10),
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Class")),
                        ft.DataColumn(ft.Text("Product")),
                        ft.DataColumn(ft.Text("SKU")),
                        ft.DataColumn(ft.Text("Usage Qty")),
                        ft.DataColumn(ft.Text("Usage Value")),
                        ft.DataColumn(ft.Text("Cumulative %")),
                    ],
                    rows=rows[:50],  # Limit to 50 for performance
                    heading_row_color="#2d3033",
                ),
                ft.Text(f"Showing {min(50, len(rows))} of {len(rows)} items", color="grey", size=12),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _build_forecasts(self):
        """Build demand forecasts table with advanced controls."""
        items = self.forecast_data.get("forecasts", []) if self.forecast_data else []

        # Build forecast control panel
        alpha_slider = ft.Slider(
            min=0.1,
            max=0.9,
            value=self.smoothing_alpha,
            divisions=8,
            label="{value}",
            on_change=self._on_alpha_change,
            width=200,
        )
        
        seasonality_switch = ft.Switch(
            value=self.seasonality_enabled,
            on_change=self._on_seasonality_toggle,
        )
        
        control_panel = ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text("Smoothing Alpha (α)", size=12, color="grey"),
                            ft.Row([
                                ft.Text("0.1", size=10, color="grey"),
                                alpha_slider,
                                ft.Text("0.9", size=10, color="grey"),
                            ], spacing=5),
                            ft.Text(
                                "Lower = More history weight, Higher = More recent data weight",
                                size=10, color="grey", italic=True
                            ),
                        ],
                    ),
                    ft.VerticalDivider(color="#3d4043"),
                    ft.Column(
                        [
                            ft.Text("Day-of-Week Seasonality", size=12, color="grey"),
                            ft.Row([
                                seasonality_switch,
                                ft.Text("Enabled" if self.seasonality_enabled else "Disabled", color="white"),
                            ]),
                        ],
                    ),
                    ft.Container(expand=True),
                    ft.ElevatedButton(
                        "Recompute Forecast",
                        icon=icons.CALCULATE,
                        bgcolor="#bb86fc",
                        color="black",
                        on_click=self._trigger_forecast_refresh,
                    ),
                ],
                spacing=30,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=15,
            bgcolor="#2d3033",
            border_radius=10,
        )
        
        # Confidence summary
        if self.forecast_data:
            high_conf = self.forecast_data.get("high_confidence_count", 0)
            med_conf = self.forecast_data.get("medium_confidence_count", 0)
            low_conf = self.forecast_data.get("low_confidence_count", 0)
        else:
            high_conf = med_conf = low_conf = 0
        
        confidence_summary = ft.Row(
            [
                self._build_confidence_badge("High", high_conf, "#4caf50"),
                self._build_confidence_badge("Medium", med_conf, "#ff9800"),
                self._build_confidence_badge("Low", low_conf, "#f44336"),
            ],
            spacing=15,
        )

        if not items:
            return ft.Column(
                [
                    ft.Text("Demand Forecasts", size=20, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Container(height=10),
                    control_panel,
                    ft.Container(height=20),
                    ft.Text("No forecast data available. Click 'Recompute Forecast' to generate.", color="grey"),
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            )

        rows = []
        for item in items:
            stockout_days = item.get("days_until_stockout")
            stockout_color = "#f44336" if stockout_days and stockout_days < 7 else "#ff9800" if stockout_days and stockout_days < 14 else "#4caf50"

            reorder_date = item.get("recommended_reorder_date", "N/A")
            if reorder_date and len(reorder_date) > 10:
                reorder_date = reorder_date[:10]
            
            # Get confidence and method
            confidence = item.get("confidence", "medium")
            conf_color = {"high": "#4caf50", "medium": "#ff9800", "low": "#f44336"}.get(confidence, "#ff9800")
            
            method = item.get("forecast_method", "exponential_smoothing")
            method_display = "ES+S" if "seasonal" in method else "ES"

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item.get("name", "")[:25], color="white")),
                        ft.DataCell(ft.Text(item.get("sku", ""), color="grey")),
                        ft.DataCell(ft.Text(str(item.get("quantity_on_hand", 0)), color="white")),
                        ft.DataCell(
                            ft.Column([
                                ft.Text(
                                    f"{self._safe_float(item.get('daily_demand_smoothed', item.get('daily_demand', 0)), 0.0):.1f}/day",
                                    color="white",
                                ),
                                ft.Text(
                                    f"raw: {self._safe_float(item.get('daily_demand', 0), 0.0):.1f}",
                                    size=10,
                                    color="grey",
                                ),
                            ], spacing=0)
                        ),
                        ft.DataCell(
                            ft.Text(
                                f"{stockout_days:.0f} days" if stockout_days and stockout_days < 9999 else "∞",
                                color=stockout_color,
                            )
                        ),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(confidence[:1].upper(), color="white", size=10),
                                width=20,
                                height=20,
                                bgcolor=conf_color,
                                border_radius=10,
                                alignment=ft.alignment.center,
                            )
                        ),
                        ft.DataCell(ft.Text(method_display, color="grey", size=12)),
                        ft.DataCell(ft.Text(str(item.get("recommended_order", 0)), color="#4caf50")),
                    ]
                )
            )

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column([
                            ft.Text("Demand Forecasts", size=20, weight=ft.FontWeight.BOLD, color="white"),
                            ft.Text(f"TTL: {self.forecast_data.get('ttl_minutes', 0) if self.forecast_data else 0} min | α={self.forecast_data.get('smoothing_alpha', 0.3) if self.forecast_data else 0.3}", size=12, color="grey"),
                        ]),
                        ft.Container(expand=True),
                        confidence_summary,
                    ],
                ),
                ft.Container(height=10),
                control_panel,
                ft.Container(height=15),
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Product")),
                        ft.DataColumn(ft.Text("SKU")),
                        ft.DataColumn(ft.Text("On Hand")),
                        ft.DataColumn(ft.Text("Demand (Smoothed)")),
                        ft.DataColumn(ft.Text("Stockout")),
                        ft.DataColumn(ft.Text("Conf")),
                        ft.DataColumn(ft.Text("Method")),
                        ft.DataColumn(ft.Text("Order Qty")),
                    ],
                    rows=rows[:50],
                    heading_row_color="#2d3033",
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
    
    def _build_confidence_badge(self, label, count, color):
        """Build a confidence level badge."""
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    width=12,
                    height=12,
                    bgcolor=color,
                    border_radius=6,
                ),
                ft.Text(f"{label}: {count}", color="white", size=12),
            ], spacing=5),
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            bgcolor="#2d3033",
            border_radius=15,
        )
    
    def _on_alpha_change(self, e):
        """Handle smoothing alpha slider change."""
        self.smoothing_alpha = round(e.control.value, 1)
    
    def _on_seasonality_toggle(self, e):
        """Handle seasonality toggle."""
        self.seasonality_enabled = e.control.value
        self._render_tab_content()
    
    def _trigger_forecast_refresh(self, e):
        """Trigger forecast recomputation with current parameters."""
        if self.page:
            self.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text(f"Refreshing forecast with α={self.smoothing_alpha}, seasonality={'on' if self.seasonality_enabled else 'off'}..."),
                    bgcolor="#bb86fc",
                )
            )
        
        try:
            result = api_service.refresh_inventory_forecast(
                smoothing_alpha=self.smoothing_alpha,
                seasonality=self.seasonality_enabled,
            )
            
            if result:
                # Reload forecast data
                self.forecast_data = api_service.get_inventory_forecast()
                self._render_tab_content()
                
                if self.page:
                    self.page.show_snack_bar(
                        ft.SnackBar(
                            content=ft.Text("Forecast refreshed successfully!"),
                            bgcolor="#4caf50",
                        )
                    )
            else:
                if self.page:
                    self.page.show_snack_bar(
                        ft.SnackBar(
                            content=ft.Text("Failed to refresh forecast"),
                            bgcolor="#f44336",
                        )
                    )
        except Exception as ex:
            print(f"Forecast refresh error: {ex}")
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Text(f"Error: {str(ex)}"),
                        bgcolor="#f44336",
                    )
                )

    def _build_po_suggestions(self):
        """Build purchase order suggestions table."""
        items = self.suggestions_data.get("suggestions", []) if self.suggestions_data else []

        if not items:
            return ft.Column(
                [
                    ft.Icon(icons.CHECK_CIRCLE, color="#4caf50", size=60),
                    ft.Text("No purchase orders needed!", size=18, color="white"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )

        total_cost = sum(float(item.get("estimated_cost", 0)) for item in items)

        rows = []
        for item in items:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item.get("name", ""), color="white")),
                        ft.DataCell(ft.Text(item.get("sku", ""), color="grey")),
                        ft.DataCell(ft.Text(str(item.get("quantity_on_hand", 0)), color="#f44336")),
                        ft.DataCell(ft.Text(str(item.get("recommended_order", 0)), color="#4caf50")),
                        ft.DataCell(ft.Text(f"${item.get('purchase_price', 0)}", color="grey")),
                        ft.DataCell(ft.Text(f"${item.get('estimated_cost', 0)}", color="#bb86fc")),
                    ]
                )
            )

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("Purchase Suggestions", size=20, weight=ft.FontWeight.BOLD, color="white"),
                                ft.Text(f"{len(items)} items need reordering", size=14, color="grey"),
                            ]
                        ),
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text("Estimated Total", size=12, color="grey"),
                                    ft.Text(f"${total_cost:,.2f}", size=24, weight=ft.FontWeight.BOLD, color="#bb86fc"),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                            ),
                            padding=15,
                            bgcolor="#2d3033",
                            border_radius=10,
                        ),
                    ],
                ),
                ft.Container(height=10),
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Product")),
                        ft.DataColumn(ft.Text("SKU")),
                        ft.DataColumn(ft.Text("On Hand")),
                        ft.DataColumn(ft.Text("Order Qty")),
                        ft.DataColumn(ft.Text("Unit Cost")),
                        ft.DataColumn(ft.Text("Total Cost")),
                    ],
                    rows=rows,
                    heading_row_color="#2d3033",
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _build_vendor_scorecard(self):
        """Build vendor/supplier performance scorecard."""
        vendors = self.vendor_data.get("vendors", []) if self.vendor_data else []

        if not vendors:
            return ft.Column(
                [
                    ft.Icon(icons.BUSINESS, color="grey", size=60),
                    ft.Text("No vendor performance data available", size=18, color="white"),
                    ft.Text("Vendor metrics are calculated from purchase order history", size=14, color="grey"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )

        rows = []
        for vendor in vendors:
            on_time_pct = vendor.get("on_time_delivery_rate", 0) * 100
            quality_pct = vendor.get("quality_score", 0) * 100
            fill_rate_pct = vendor.get("fill_rate", 0) * 100
            avg_lead = vendor.get("avg_lead_time_days", 0)
            
            # Color coding based on performance
            on_time_color = "#4caf50" if on_time_pct >= 90 else "#ff9800" if on_time_pct >= 70 else "#f44336"
            quality_color = "#4caf50" if quality_pct >= 95 else "#ff9800" if quality_pct >= 80 else "#f44336"
            
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(vendor.get("name", ""), color="white")),
                        ft.DataCell(ft.Text(str(vendor.get("total_orders", 0)), color="grey")),
                        ft.DataCell(ft.Text(f"${vendor.get('total_spend', 0):,.2f}", color="#bb86fc")),
                        ft.DataCell(ft.Text(f"{avg_lead:.1f} days", color="white")),
                        ft.DataCell(ft.Text(f"{on_time_pct:.0f}%", color=on_time_color)),
                        ft.DataCell(ft.Text(f"{quality_pct:.0f}%", color=quality_color)),
                        ft.DataCell(ft.Text(f"{fill_rate_pct:.0f}%", color="white")),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text("★" if vendor.get("is_preferred") else "", color="#ffc107"),
                                alignment=ft.alignment.center,
                            )
                        ),
                    ]
                )
            )

        # Summary metrics
        total_vendors = len(vendors)
        avg_on_time = sum(v.get("on_time_delivery_rate", 0) for v in vendors) / max(1, total_vendors) * 100
        total_spend = sum(v.get("total_spend", 0) for v in vendors)

        return ft.Column(
            [
                ft.Text("Vendor Performance Scorecard", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                ft.Row(
                    [
                        self._build_metric_card("Total Vendors", str(total_vendors), icons.BUSINESS, "#2196f3"),
                        self._build_metric_card("Avg On-Time", f"{avg_on_time:.0f}%", icons.SCHEDULE, "#4caf50"),
                        self._build_metric_card("Total Spend", f"${total_spend:,.0f}", icons.ATTACH_MONEY, "#bb86fc"),
                    ],
                    wrap=True,
                    spacing=20,
                ),
                ft.Container(height=20),
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Vendor")),
                        ft.DataColumn(ft.Text("Orders")),
                        ft.DataColumn(ft.Text("Spend")),
                        ft.DataColumn(ft.Text("Lead Time")),
                        ft.DataColumn(ft.Text("On-Time %")),
                        ft.DataColumn(ft.Text("Quality")),
                        ft.DataColumn(ft.Text("Fill Rate")),
                        ft.DataColumn(ft.Text("Preferred")),
                    ],
                    rows=rows,
                    heading_row_color="#2d3033",
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _build_po_drafts(self):
        """Build purchase order drafts view."""
        lines = self.po_drafts_data.get("lines", []) if self.po_drafts_data else []
        total_estimated = self.po_drafts_data.get("total_estimated", 0) if self.po_drafts_data else 0
        supplier = self.po_drafts_data.get("supplier") if self.po_drafts_data else None
        is_capped = self.po_drafts_data.get("capped", False) if self.po_drafts_data else False
        budget_cap = self.po_drafts_data.get("budget_cap") if self.po_drafts_data else None

        if not lines:
            return ft.Column(
                [
                    ft.Icon(icons.CHECK_CIRCLE, color="#4caf50", size=60),
                    ft.Text("No purchase orders needed!", size=18, color="white"),
                    ft.Text("All items are adequately stocked", size=14, color="grey"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )

        rows = []
        for line in lines:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(line.get("name", ""), color="white")),
                        ft.DataCell(ft.Text(line.get("sku", ""), color="grey")),
                        ft.DataCell(ft.Text(str(line.get("quantity", 0)), color="#4caf50")),
                        ft.DataCell(ft.Text(f"${line.get('unit_cost', 0)}", color="grey")),
                        ft.DataCell(ft.Text(f"${line.get('estimated_cost', 0)}", color="#bb86fc")),
                    ]
                )
            )

        # Header with supplier info
        supplier_info = ""
        if supplier:
            supplier_info = f"Supplier: {supplier.get('name', 'N/A')}"

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("Auto-Generated PO Draft", size=20, weight=ft.FontWeight.BOLD, color="white"),
                                ft.Text(supplier_info, size=14, color="grey") if supplier_info else ft.Container(),
                                ft.Text("⚠️ Budget cap applied" if is_capped else "", size=12, color="#ff9800") if is_capped else ft.Container(),
                            ]
                        ),
                        ft.Container(expand=True),
                        ft.Column(
                            [
                                ft.Container(
                                    content=ft.Column(
                                        [
                                            ft.Text("Total Estimated", size=12, color="grey"),
                                            ft.Text(f"${float(total_estimated):,.2f}", size=24, weight=ft.FontWeight.BOLD, color="#bb86fc"),
                                            ft.Text(f"Budget Cap: ${float(budget_cap):,.2f}" if budget_cap else "", size=10, color="grey"),
                                        ],
                                        horizontal_alignment=ft.CrossAxisAlignment.END,
                                    ),
                                    padding=15,
                                    bgcolor="#2d3033",
                                    border_radius=10,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                        ),
                    ],
                ),
                ft.Container(height=15),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Generate PO",
                            icon=icons.ADD_SHOPPING_CART,
                            bgcolor="#4caf50",
                            color="white",
                            on_click=self._on_generate_po,
                        ),
                        ft.ElevatedButton(
                            "Refresh Draft",
                            icon=icons.REFRESH,
                            bgcolor="#2196f3",
                            color="white",
                            on_click=self._refresh_po_drafts,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Container(height=15),
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Product")),
                        ft.DataColumn(ft.Text("SKU")),
                        ft.DataColumn(ft.Text("Order Qty")),
                        ft.DataColumn(ft.Text("Unit Cost")),
                        ft.DataColumn(ft.Text("Line Total")),
                    ],
                    rows=rows,
                    heading_row_color="#2d3033",
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _refresh_po_drafts(self, e=None):
        """Refresh PO drafts data."""
        try:
            self.po_drafts_data = api_service.get_po_drafts()
            self._render_tab_content()
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text("PO drafts refreshed"), bgcolor="#4caf50")
                )
        except Exception as ex:
            print(f"Error refreshing PO drafts: {ex}")

    def _on_generate_po(self, e=None):
        """Handle generate PO button click."""
        if self.page:
            self.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("PO generation workflow coming soon..."),
                    bgcolor="#ff9800",
                )
            )
