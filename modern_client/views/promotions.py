"""Promotions management view for Admin POS client.

Provides management for:
- Active promotions and discounts
- Seasonal sales campaigns
- Coupon codes
- BOGO offers
"""

import flet as ft
from datetime import datetime
from services.api import api_service

icons = ft.icons


class PromotionsView(ft.Container):
    """Promotions management view."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 20
        self.promotions = []
        
        # Build UI
        self.content = self._build_layout()

    def did_mount(self):
        """Load promotions when view is mounted."""
        self._load_promotions()

    def _build_layout(self):
        """Build the main promotions layout."""
        # Promotions table
        self.promotions_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Name", color="white", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Type", color="white", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Value", color="white", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", color="white", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Period", color="white", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Usage", color="white", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actions", color="white", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            border=ft.border.all(1, "#3d4043"),
            border_radius=10,
            heading_row_color="#2d3033",
            data_row_color={"hovered": "#3d4043"},
        )
        
        # Filter chips
        self.filter_all = ft.Chip(
            label=ft.Text("All"),
            selected=True,
            on_select=lambda e: self._filter_promotions("all"),
        )
        self.filter_active = ft.Chip(
            label=ft.Text("Active"),
            on_select=lambda e: self._filter_promotions("active"),
        )
        self.filter_scheduled = ft.Chip(
            label=ft.Text("Scheduled"),
            on_select=lambda e: self._filter_promotions("scheduled"),
        )
        self.filter_expired = ft.Chip(
            label=ft.Text("Expired"),
            on_select=lambda e: self._filter_promotions("expired"),
        )
        
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Promotions & Sales", size=30, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            "Create Promotion",
                            icon=icons.ADD,
                            bgcolor="#6366f1",
                            color="white",
                            on_click=self._show_create_dialog,
                        ),
                        ft.IconButton(
                            icons.REFRESH,
                            icon_color="white",
                            tooltip="Refresh",
                            on_click=lambda e: self._load_promotions(),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(color="#2d3033"),
                ft.Row(
                    [
                        ft.Text("Filter:", color="grey"),
                        self.filter_all,
                        self.filter_active,
                        self.filter_scheduled,
                        self.filter_expired,
                    ],
                    spacing=10,
                ),
                ft.Container(height=10),
                ft.Container(
                    content=self.promotions_table,
                    expand=True,
                    border_radius=10,
                ),
            ],
            expand=True,
        )

    def _load_promotions(self, filter_type: str = "all"):
        """Load promotions from API."""
        try:
            active_only = filter_type == "active"
            self.promotions = api_service.get_promotions(active_only=active_only)
            self._render_promotions()
        except Exception as e:
            print(f"Error loading promotions: {e}")
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Text(f"Error loading promotions: {e}"),
                        bgcolor="#f44336",
                    )
                )

    def _filter_promotions(self, filter_type: str):
        """Filter promotions by type."""
        self.filter_all.selected = filter_type == "all"
        self.filter_active.selected = filter_type == "active"
        self.filter_scheduled.selected = filter_type == "scheduled"
        self.filter_expired.selected = filter_type == "expired"
        self._load_promotions(filter_type)
        self.update()

    def _render_promotions(self):
        """Render promotions table."""
        rows = []
        
        for promo in self.promotions:
            rows.append(self._create_promotion_row(promo))
        
        self.promotions_table.rows = rows
        self.update()

    def _create_promotion_row(self, promo: dict):
        """Create a data row for a promotion."""
        # Extract discount info
        discount_rule = promo.get("discount_rule", {})
        discount_type = discount_rule.get("discount_type", "percentage")
        value = discount_rule.get("value", 0)
        
        # Format value display
        if discount_type == "percentage":
            value_text = f"{value}%"
        elif discount_type == "fixed":
            value_text = f"${value:.2f}"
        elif discount_type == "bogo":
            buy_qty = discount_rule.get("buy_quantity", 1)
            get_qty = discount_rule.get("get_quantity", 1)
            value_text = f"Buy {buy_qty} Get {get_qty}"
        else:
            value_text = str(value)
        
        # Status badge
        status = promo.get("status", "draft")
        status_color = {
            "active": "#4caf50",
            "scheduled": "#ff9800",
            "expired": "#9e9e9e",
            "draft": "#607d8b",
        }.get(status, "#607d8b")
        
        status_badge = ft.Container(
            content=ft.Text(status.capitalize(), color="white", size=12),
            bgcolor=status_color,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=12,
        )
        
        # Period
        start_date = promo.get("start_date", "")
        end_date = promo.get("end_date")
        period_text = start_date[:10] if start_date else "-"
        if end_date:
            period_text += f" to {end_date[:10]}"
        
        # Usage
        usage_count = promo.get("usage_count", 0)
        usage_limit = promo.get("usage_limit")
        usage_text = f"{usage_count}"
        if usage_limit:
            usage_text += f" / {usage_limit}"
        
        # Coupon code display
        coupon_code = promo.get("coupon_code")
        name_content = ft.Column(
            [
                ft.Text(promo.get("name", "Unnamed"), color="white", weight=ft.FontWeight.BOLD),
                ft.Text(f"Code: {coupon_code}" if coupon_code else "No code", color="grey", size=12),
            ],
            spacing=2,
        )
        
        return ft.DataRow(
            cells=[
                ft.DataCell(name_content),
                ft.DataCell(ft.Text(discount_type.capitalize(), color="white")),
                ft.DataCell(ft.Text(value_text, color="#bb86fc", weight=ft.FontWeight.BOLD)),
                ft.DataCell(status_badge),
                ft.DataCell(ft.Text(period_text, color="white", size=12)),
                ft.DataCell(ft.Text(usage_text, color="white")),
                ft.DataCell(
                    ft.Row(
                        [
                            ft.IconButton(
                                icons.EDIT,
                                icon_color="#6366f1",
                                tooltip="Edit",
                                on_click=lambda e, p=promo: self._show_edit_dialog(p),
                            ),
                            ft.IconButton(
                                icons.TOGGLE_ON if status != "active" else icons.TOGGLE_OFF,
                                icon_color="#4caf50" if status != "active" else "#ff9800",
                                tooltip="Activate" if status != "active" else "Deactivate",
                                on_click=lambda e, p=promo: self._toggle_promotion(p),
                            ),
                            ft.IconButton(
                                icons.DELETE,
                                icon_color="#cf6679",
                                tooltip="Delete",
                                on_click=lambda e, p=promo: self._delete_promotion(p),
                            ),
                        ],
                        spacing=0,
                    ),
                ),
            ],
        )

    def _show_create_dialog(self, e):
        """Show dialog to create a new promotion."""
        self._show_promotion_dialog(None)

    def _show_edit_dialog(self, promo: dict):
        """Show dialog to edit an existing promotion."""
        self._show_promotion_dialog(promo)

    def _show_promotion_dialog(self, promo: dict | None):
        """Show promotion create/edit dialog."""
        is_edit = promo is not None
        
        # Form fields
        name_field = ft.TextField(
            label="Promotion Name",
            value=promo.get("name", "") if promo else "",
            width=400,
            bgcolor="#2d3033",
            color="white",
        )
        
        description_field = ft.TextField(
            label="Description",
            value=promo.get("description", "") if promo else "",
            width=400,
            multiline=True,
            min_lines=2,
            max_lines=4,
            bgcolor="#2d3033",
            color="white",
        )
        
        discount_type_dropdown = ft.Dropdown(
            label="Discount Type",
            value=promo.get("discount_rule", {}).get("discount_type", "percentage") if promo else "percentage",
            options=[
                ft.dropdown.Option(key="percentage", text="Percentage Off"),
                ft.dropdown.Option(key="fixed", text="Fixed Amount Off"),
                ft.dropdown.Option(key="bogo", text="Buy X Get Y (BOGO)"),
            ],
            width=200,
            bgcolor="#2d3033",
        )
        
        value_field = ft.TextField(
            label="Value",
            value=str(promo.get("discount_rule", {}).get("value", "")) if promo else "",
            width=100,
            bgcolor="#2d3033",
            color="white",
        )
        
        coupon_code_field = ft.TextField(
            label="Coupon Code (optional)",
            value=promo.get("coupon_code", "") if promo else "",
            width=200,
            bgcolor="#2d3033",
            color="white",
        )
        
        usage_limit_field = ft.TextField(
            label="Usage Limit",
            value=str(promo.get("usage_limit", "")) if promo and promo.get("usage_limit") else "",
            width=100,
            bgcolor="#2d3033",
            color="white",
            hint_text="Unlimited",
        )
        
        def on_save(e):
            """Save the promotion."""
            try:
                # Build discount rule
                discount_rule = {
                    "discount_type": discount_type_dropdown.value,
                    "value": float(value_field.value) if value_field.value else 0,
                    "target": "order",
                }
                
                payload = {
                    "name": name_field.value,
                    "description": description_field.value or "",
                    "discount_rule": discount_rule,
                    "start_date": datetime.utcnow().isoformat(),
                    "coupon_code": coupon_code_field.value or None,
                    "usage_limit": int(usage_limit_field.value) if usage_limit_field.value else None,
                }
                
                if is_edit:
                    result = api_service.update_promotion(promo["id"], payload)
                else:
                    result = api_service.create_promotion(payload)
                
                if result:
                    dialog.open = False
                    self.page.update()
                    self._load_promotions()
                    self.page.show_snack_bar(
                        ft.SnackBar(
                            content=ft.Text(f"Promotion {'updated' if is_edit else 'created'} successfully!"),
                            bgcolor="#4caf50",
                        )
                    )
            except Exception as ex:
                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"Error: {ex}"), bgcolor="#f44336")
                )
        
        def on_cancel(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Edit Promotion" if is_edit else "Create Promotion"),
            content=ft.Container(
                width=450,
                height=400,
                content=ft.Column(
                    [
                        name_field,
                        description_field,
                        ft.Row([discount_type_dropdown, value_field], spacing=20),
                        coupon_code_field,
                        usage_limit_field,
                    ],
                    spacing=15,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton(
                    "Save",
                    icon=icons.SAVE,
                    bgcolor="#6366f1",
                    color="white",
                    on_click=on_save,
                ),
            ],
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _toggle_promotion(self, promo: dict):
        """Toggle promotion active status."""
        try:
            promo_id = promo["id"]
            status = promo.get("status", "draft")
            
            if status == "active":
                result = api_service.deactivate_promotion(promo_id)
                message = "Promotion deactivated"
            else:
                result = api_service.activate_promotion(promo_id)
                message = "Promotion activated"
            
            if result:
                self._load_promotions()
                if self.page:
                    self.page.show_snack_bar(
                        ft.SnackBar(content=ft.Text(message), bgcolor="#4caf50")
                    )
        except Exception as ex:
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"Error: {ex}"), bgcolor="#f44336")
                )

    def _delete_promotion(self, promo: dict):
        """Delete a promotion."""
        def confirm_delete(e):
            try:
                result = api_service.delete_promotion(promo["id"])
                if result:
                    dialog.open = False
                    self.page.update()
                    self._load_promotions()
                    self.page.show_snack_bar(
                        ft.SnackBar(content=ft.Text("Promotion deleted"), bgcolor="#4caf50")
                    )
            except Exception as ex:
                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"Error: {ex}"), bgcolor="#f44336")
                )
        
        def cancel_delete(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Delete Promotion?"),
            content=ft.Text(f"Are you sure you want to delete '{promo.get('name', 'this promotion')}'?"),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_delete),
                ft.ElevatedButton(
                    "Delete",
                    bgcolor="#cf6679",
                    color="white",
                    on_click=confirm_delete,
                ),
            ],
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
