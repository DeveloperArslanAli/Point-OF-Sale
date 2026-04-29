import flet as ft
from services.api import api_client


class DashboardView(ft.Container):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 20
        self.tenants_data = []  # Store tenant data for branding

        # Stats cards (will be updated)
        self.tenants_count_card = self._build_card("Tenants", "0", ft.icons.BUSINESS)
        self.revenue_card = self._build_card("Total Revenue", "$0.00", ft.icons.MONEY)
        self.health_card = self._build_card("System Health", "Good", ft.icons.HEALTH_AND_SAFETY)
        self.active_card = self._build_card("Active", "0", ft.icons.CHECK_CIRCLE)

        self.tenants_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Logo")),
                ft.DataColumn(ft.Text("Name")),
                ft.DataColumn(ft.Text("Domain")),
                ft.DataColumn(ft.Text("Plan")),
                ft.DataColumn(ft.Text("Status")),
                ft.DataColumn(ft.Text("Actions")),
            ],
            rows=[],
        )

        self.plans_container = ft.Row(wrap=True, spacing=20)

        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("SuperAdmin Dashboard", size=30, weight="bold"),
                        ft.IconButton(ft.icons.REFRESH, on_click=self._refresh_data),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(),
                ft.Row(
                    [
                        self.tenants_count_card,
                        self.revenue_card,
                        self.health_card,
                        self.active_card,
                    ],
                    wrap=True,
                ),
                ft.Container(height=20),
                ft.Text("Subscription Plans", size=20, weight="bold"),
                self.plans_container,
                ft.Container(height=20),
                ft.Row(
                    [
                        ft.Text("Tenant Management", size=20, weight="bold"),
                        ft.ElevatedButton(
                            "Create Tenant", icon=ft.icons.ADD, on_click=self._open_create_dialog
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.tenants_table,
            ],
            scroll=ft.ScrollMode.AUTO,
        )
        
        # Create Tenant Dialog Components
        self.new_tenant_name = ft.TextField(label="Tenant Name")
        self.new_tenant_domain = ft.TextField(label="Custom Domain (Optional)")
        self.plan_dropdown = ft.Dropdown(label="Select Plan", options=[])
        self.create_dialog = ft.AlertDialog(
            title=ft.Text("Create New Tenant"),
            content=ft.Column(
                [self.new_tenant_name, self.new_tenant_domain, self.plan_dropdown], height=200
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self._close_create_dialog),
                ft.ElevatedButton("Create", on_click=self._create_tenant),
            ],
        )

        # Branding Dialog Components
        self.branding_tenant_id = None
        self.branding_logo_url = ft.TextField(label="Logo URL")
        self.branding_company_name = ft.TextField(label="Company Name")
        self.branding_primary_color = ft.TextField(label="Primary Color (hex)", value="#1976D2")
        self.branding_secondary_color = ft.TextField(label="Secondary Color (hex)", value="#424242")
        self.branding_tagline = ft.TextField(label="Tagline (Optional)")
        self.branding_dialog = ft.AlertDialog(
            title=ft.Text("Configure Tenant Branding"),
            content=ft.Column(
                [
                    self.branding_logo_url,
                    self.branding_company_name,
                    self.branding_primary_color,
                    self.branding_secondary_color,
                    self.branding_tagline,
                ],
                height=300,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self._close_branding_dialog),
                ft.ElevatedButton("Save Branding", on_click=self._save_branding),
            ],
        )

        # Suspend Dialog
        self.suspend_tenant_id = None
        self.suspend_reason = ft.TextField(label="Reason for Suspension", multiline=True)
        self.suspend_dialog = ft.AlertDialog(
            title=ft.Text("Suspend Tenant"),
            content=ft.Column([self.suspend_reason], height=100),
            actions=[
                ft.TextButton("Cancel", on_click=self._close_suspend_dialog),
                ft.ElevatedButton("Suspend", on_click=self._confirm_suspend, bgcolor="red"),
            ],
        )

    def did_mount(self):
        self._refresh_data(None)

    def _refresh_data(self, e):
        # Fetch System Stats
        stats = api_client.get_system_stats()
        if stats:
            self._update_card(self.tenants_count_card, str(stats.get("total_tenants", 0)))
            self._update_card(
                self.revenue_card, f"${stats.get('total_revenue', 0):,.2f}"
            )
            self._update_card(self.active_card, str(stats.get("active_tenants", 0)))
            health_status = "Good" if stats.get("system_healthy", True) else "Issues"
            self._update_card(self.health_card, health_status)

        # Fetch Plans
        plans = api_client.get_plans()
        self.plans_container.controls = [self._build_plan_card(p) for p in plans]

        # Update Dropdown
        self.plan_dropdown.options = [
            ft.dropdown.Option(key=p["id"], text=f"{p['name']} (${p['price']})")
            for p in plans
        ]

        # Build plan lookup
        plan_lookup = {p["id"]: p["name"] for p in plans}

        # Fetch Tenants
        tenants = api_client.get_tenants()
        self.tenants_data = tenants  # Store for branding
        self.tenants_table.rows = [
            self._build_tenant_row(t, plan_lookup) for t in tenants
        ]
        self.update()

    def _update_card(self, card, value):
        """Update a stat card's value."""
        # The value is in the last Text element of the card's column
        card.content.controls[2].value = value

    def _build_tenant_row(self, tenant, plan_lookup):
        """Build a DataRow for a tenant with actions."""
        is_active = tenant.get("active", False)
        tenant_id = tenant["id"]
        plan_name = plan_lookup.get(tenant.get("subscription_plan_id", ""), "Unknown")

        # Logo preview (placeholder if no logo)
        logo = ft.Container(
            width=40,
            height=40,
            border_radius=5,
            bgcolor="#3d4043",
            content=ft.Icon(ft.icons.BUSINESS, size=20),
        )

        # Status badge
        status_badge = ft.Container(
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=12,
            bgcolor="#4caf50" if is_active else "#f44336",
            content=ft.Text(
                "Active" if is_active else "Suspended",
                size=11,
                color="white",
            ),
        )

        # Action buttons
        actions = ft.Row(
            [
                ft.IconButton(
                    ft.icons.PALETTE,
                    tooltip="Configure Branding",
                    on_click=lambda e, tid=tenant_id: self._open_branding_dialog(tid),
                ),
                ft.IconButton(
                    ft.icons.SETTINGS,
                    tooltip="View Settings",
                    on_click=lambda e, tid=tenant_id: self._view_tenant_settings(tid),
                ),
                ft.IconButton(
                    ft.icons.PAUSE if is_active else ft.icons.PLAY_ARROW,
                    tooltip="Suspend" if is_active else "Reactivate",
                    on_click=lambda e, tid=tenant_id, active=is_active: (
                        self._open_suspend_dialog(tid) if active else self._reactivate_tenant(tid)
                    ),
                ),
            ],
            spacing=0,
        )

        return ft.DataRow(
            cells=[
                ft.DataCell(logo),
                ft.DataCell(ft.Text(tenant["name"])),
                ft.DataCell(ft.Text(tenant.get("domain") or "-")),
                ft.DataCell(ft.Text(plan_name)),
                ft.DataCell(status_badge),
                ft.DataCell(actions),
            ]
        )

    def _build_plan_card(self, plan):
        return ft.Container(
            width=250,
            padding=15,
            bgcolor="#2d3033",
            border_radius=10,
            content=ft.Column(
                [
                    ft.Text(plan["name"], size=18, weight="bold"),
                    ft.Text(f"${plan['price']}", size=24, color="green"),
                    ft.Text(f"{plan['duration_months']} Months", size=12, italic=True),
                    ft.Text(plan.get("description") or "", size=12),
                ]
            ),
        )

    def _open_create_dialog(self, e):
        self.app.page.dialog = self.create_dialog
        self.create_dialog.open = True
        self.app.page.update()

    def _close_create_dialog(self, e):
        self.create_dialog.open = False
        self.app.page.update()

    def _create_tenant(self, e):
        if not self.new_tenant_name.value or not self.plan_dropdown.value:
            return  # Validation

        res = api_client.create_tenant(
            name=self.new_tenant_name.value,
            subscription_plan_id=self.plan_dropdown.value,
            domain=self.new_tenant_domain.value,
        )

        if res:
            self._close_create_dialog(None)
            self._refresh_data(None)
            self.new_tenant_name.value = ""
            self.new_tenant_domain.value = ""
            self.plan_dropdown.value = None

    # ===================
    # Branding Management
    # ===================

    def _open_branding_dialog(self, tenant_id):
        """Open branding dialog for a tenant."""
        self.branding_tenant_id = tenant_id

        # Pre-fill with existing settings if available
        settings = api_client.get_tenant_settings(tenant_id)
        if settings:
            branding = settings.get("branding", {})
            self.branding_logo_url.value = branding.get("logo_url", "")
            self.branding_company_name.value = branding.get("company_name", "")
            self.branding_primary_color.value = branding.get("primary_color", "#1976D2")
            self.branding_secondary_color.value = branding.get("secondary_color", "#424242")
            self.branding_tagline.value = branding.get("tagline", "")

        self.app.page.dialog = self.branding_dialog
        self.branding_dialog.open = True
        self.app.page.update()

    def _close_branding_dialog(self, e):
        self.branding_dialog.open = False
        self.branding_tenant_id = None
        self.app.page.update()

    def _save_branding(self, e):
        """Save branding for the selected tenant."""
        if not self.branding_tenant_id:
            return

        branding = {
            "logo_url": self.branding_logo_url.value or None,
            "company_name": self.branding_company_name.value or None,
            "primary_color": self.branding_primary_color.value,
            "secondary_color": self.branding_secondary_color.value,
            "tagline": self.branding_tagline.value or None,
        }

        res = api_client.set_tenant_branding(self.branding_tenant_id, branding)
        if res:
            self._close_branding_dialog(None)
            self._show_snackbar("Branding updated successfully")
            self._refresh_data(None)
        else:
            self._show_snackbar("Failed to update branding", error=True)

    # ===================
    # Tenant Suspension
    # ===================

    def _open_suspend_dialog(self, tenant_id):
        """Open suspend dialog for a tenant."""
        self.suspend_tenant_id = tenant_id
        self.suspend_reason.value = ""
        self.app.page.dialog = self.suspend_dialog
        self.suspend_dialog.open = True
        self.app.page.update()

    def _close_suspend_dialog(self, e):
        self.suspend_dialog.open = False
        self.suspend_tenant_id = None
        self.app.page.update()

    def _confirm_suspend(self, e):
        """Suspend the selected tenant."""
        if not self.suspend_tenant_id:
            return

        reason = self.suspend_reason.value or "No reason provided"
        res = api_client.suspend_tenant(self.suspend_tenant_id, reason)
        if res:
            self._close_suspend_dialog(None)
            self._show_snackbar("Tenant suspended")
            self._refresh_data(None)
        else:
            self._show_snackbar("Failed to suspend tenant", error=True)

    def _reactivate_tenant(self, tenant_id):
        """Reactivate a suspended tenant."""
        res = api_client.reactivate_tenant(tenant_id)
        if res:
            self._show_snackbar("Tenant reactivated")
            self._refresh_data(None)
        else:
            self._show_snackbar("Failed to reactivate tenant", error=True)

    def _view_tenant_settings(self, tenant_id):
        """View detailed settings for a tenant."""
        settings = api_client.get_tenant_settings(tenant_id)
        if settings:
            # Show settings in a dialog
            content = ft.Column(
                [
                    ft.Text("Branding", weight="bold"),
                    ft.Text(f"Company: {settings.get('branding', {}).get('company_name', 'Not set')}"),
                    ft.Text(f"Logo: {'Set' if settings.get('branding', {}).get('logo_url') else 'Not set'}"),
                    ft.Divider(),
                    ft.Text("Currency", weight="bold"),
                    ft.Text(f"Currency: {settings.get('currency', {}).get('code', 'USD')}"),
                    ft.Divider(),
                    ft.Text("Tax", weight="bold"),
                    ft.Text(
                        f"Tax Inclusive: {'Yes' if settings.get('tax', {}).get('inclusive_pricing') else 'No'}"
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
                height=300,
            )
            dialog = ft.AlertDialog(
                title=ft.Text("Tenant Settings Overview"),
                content=content,
                actions=[ft.TextButton("Close", on_click=lambda e: self._close_dialog(dialog))],
            )
            self.app.page.dialog = dialog
            dialog.open = True
            self.app.page.update()

    def _close_dialog(self, dialog):
        dialog.open = False
        self.app.page.update()

    def _show_snackbar(self, message, error=False):
        """Show a snackbar notification."""
        self.app.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor="red" if error else "green",
        )
        self.app.page.snack_bar.open = True
        self.app.page.update()

    def _build_card(self, title, value, icon):
        return ft.Container(
            width=200,
            height=100,
            bgcolor="#2d3033",
            border_radius=10,
            padding=10,
            content=ft.Column(
                [
                    ft.Icon(icon),
                    ft.Text(title, size=12, color="grey"),
                    ft.Text(value, size=20, weight="bold"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
