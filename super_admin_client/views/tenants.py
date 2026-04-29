"""Tenants management view."""
import flet as ft

from config import config
from services.api_v2 import api_client
from components.data_table import DataTable, DataTableColumn
from components.badge import StatusBadge
from components.dialogs import ConfirmDialog, FormDialog, show_snackbar


class TenantsView(ft.Container):
    """Tenant list and management view."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        
        self._current_page = 1
        self._page_size = 10
        self._total_items = 0
        self._tenants = []
        self._plans = []
        self._filter_active_only = False
        
        self._build()
    
    def _build(self):
        """Build the tenants view layout."""
        # Action bar
        self.filter_active = ft.Checkbox(
            label="Active only",
            value=False,
            on_change=self._on_filter_change,
        )
        
        action_bar = ft.Row(
            [
                self.filter_active,
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    icon_color="white",
                    tooltip="Refresh",
                    on_click=lambda e: self._load_tenants(),
                ),
                ft.ElevatedButton(
                    "Create Tenant",
                    icon=ft.Icons.ADD,
                    bgcolor=config.PRIMARY_COLOR,
                    color="white",
                    on_click=self._open_create_dialog,
                ),
            ],
        )
        
        # Data table columns
        columns = [
            DataTableColumn(
                key="logo",
                label="",
                width=60,
                sortable=False,
                render=self._render_logo,
            ),
            DataTableColumn(
                key="name",
                label="Name",
                width=200,
                render=self._render_name,
            ),
            DataTableColumn(
                key="slug",
                label="Slug",
                width=150,
            ),
            DataTableColumn(
                key="subscription_plan",
                label="Plan",
                width=120,
            ),
            DataTableColumn(
                key="is_active",
                label="Status",
                width=100,
                render=self._render_status,
            ),
            DataTableColumn(
                key="user_count",
                label="Users",
                width=80,
            ),
            DataTableColumn(
                key="actions",
                label="Actions",
                width=180,
                sortable=False,
                render=self._render_actions,
            ),
        ]
        
        self.data_table = DataTable(
            columns=columns,
            data=[],
            page_size=self._page_size,
            on_page_change=self._on_page_change,
            on_search=self._on_search,
            loading=True,
            empty_message="No tenants found",
        )
        
        self.content = ft.Column(
            [
                action_bar,
                ft.Container(height=15),
                self.data_table,
            ],
            expand=True,
        )
        
        # Create dialog components
        self._create_dialogs()
    
    def _create_dialogs(self):
        """Create dialog components."""
        # Create tenant dialog
        self.new_tenant_name = ft.TextField(
            label="Tenant Name",
            data="name",
        )
        self.new_tenant_domain = ft.TextField(
            label="Custom Domain (Optional)",
            data="domain",
        )
        self.plan_dropdown = ft.Dropdown(
            label="Subscription Plan",
            data="plan_id",
            options=[],
        )
        
        self.create_dialog = FormDialog(
            title="Create New Tenant",
            fields=[
                self.new_tenant_name,
                self.new_tenant_domain,
                self.plan_dropdown,
            ],
            on_submit=self._create_tenant,
            width=400,
        )
        
        # Branding dialog
        self.branding_tenant_id = None
        self.branding_logo_url = ft.TextField(label="Logo URL", data="logo_url")
        self.branding_company_name = ft.TextField(label="Company Name", data="company_name")
        self.branding_primary_color = ft.TextField(label="Primary Color (hex)", value="#6366f1", data="primary_color")
        self.branding_secondary_color = ft.TextField(label="Secondary Color (hex)", value="#8b5cf6", data="secondary_color")
        
        self.branding_dialog = FormDialog(
            title="Configure Tenant Branding",
            fields=[
                self.branding_logo_url,
                self.branding_company_name,
                self.branding_primary_color,
                self.branding_secondary_color,
            ],
            on_submit=self._save_branding,
            width=400,
        )
        
        # Suspend dialog
        self.suspend_tenant_id = None
        self.suspend_reason = ft.TextField(
            label="Reason for Suspension",
            multiline=True,
            min_lines=2,
            max_lines=4,
            data="reason",
        )
        
        self.suspend_dialog = FormDialog(
            title="Suspend Tenant",
            fields=[
                ft.Text("This will disable all access for this tenant.", color="grey"),
                self.suspend_reason,
            ],
            submit_text="Suspend",
            on_submit=self._confirm_suspend,
            width=400,
        )
    
    def _render_logo(self, row: dict) -> ft.Control:
        """Render tenant logo cell."""
        return ft.Container(
            content=ft.Icon(ft.Icons.BUSINESS, size=20, color="grey"),
            width=40,
            height=40,
            border_radius=8,
            bgcolor="#3d4043",
            alignment=ft.alignment.center,
        )
    
    def _render_name(self, row: dict) -> ft.Control:
        """Render tenant name cell."""
        return ft.Text(
            row.get("name", "Unknown"),
            weight=ft.FontWeight.W_500,
            color="white",
        )
    
    def _render_status(self, row: dict) -> ft.Control:
        """Render status badge."""
        is_active = row.get("is_active", False)
        return StatusBadge("active" if is_active else "suspended")
    
    def _render_actions(self, row: dict) -> ft.Control:
        """Render action buttons."""
        tenant_id = row.get("id")
        is_active = row.get("is_active", False)
        
        return ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.PALETTE,
                    icon_size=18,
                    tooltip="Configure Branding",
                    on_click=lambda e, tid=tenant_id: self._open_branding_dialog(tid),
                ),
                ft.IconButton(
                    icon=ft.Icons.SETTINGS,
                    icon_size=18,
                    tooltip="View Settings",
                    on_click=lambda e, tid=tenant_id: self._view_settings(tid),
                ),
                ft.IconButton(
                    icon=ft.Icons.PAUSE if is_active else ft.Icons.PLAY_ARROW,
                    icon_size=18,
                    tooltip="Suspend" if is_active else "Reactivate",
                    icon_color=config.WARNING_COLOR if is_active else config.SUCCESS_COLOR,
                    on_click=lambda e, tid=tenant_id, active=is_active: (
                        self._open_suspend_dialog(tid) if active else self._reactivate_tenant(tid)
                    ),
                ),
            ],
            spacing=0,
        )
    
    def did_mount(self):
        """Load data on mount."""
        self._load_plans()
        self._load_tenants()
    
    def _load_plans(self):
        """Load subscription plans for dropdown."""
        self._plans = api_client.get_subscription_plans()
        
        self.plan_dropdown.options = [
            ft.dropdown.Option(
                key=plan.get("id"),
                text=f"{plan.get('name')} (${plan.get('price_monthly', plan.get('price', 0))})"
            )
            for plan in self._plans
        ]
    
    def _load_tenants(self):
        """Load tenants data."""
        self.data_table.set_loading(True)
        
        result = api_client.get_all_tenants(
            page=self._current_page,
            page_size=self._page_size,
            active_only=self._filter_active_only,
        )
        
        if result and not result.get("error"):
            self._tenants = result.get("items", [])
            self._total_items = result.get("total", 0)
            
            self.data_table.set_data(self._tenants, self._total_items)
        else:
            show_snackbar(self.app.page, "Failed to load tenants", error=True)
            self.data_table.set_loading(False)
    
    def _on_page_change(self, page: int):
        """Handle page change."""
        self._current_page = page
        self._load_tenants()
    
    def _on_filter_change(self, e):
        """Handle filter change."""
        self._filter_active_only = e.control.value
        self._current_page = 1
        self._load_tenants()
    
    def _on_search(self, query: str):
        """Handle search (client-side filter for now)."""
        if not query:
            self.data_table.set_data(self._tenants, self._total_items)
            return
        
        filtered = [
            t for t in self._tenants
            if query.lower() in t.get("name", "").lower()
            or query.lower() in t.get("slug", "").lower()
        ]
        self.data_table.set_data(filtered, len(filtered))
    
    def _open_create_dialog(self, e):
        """Open create tenant dialog."""
        self.new_tenant_name.value = ""
        self.new_tenant_domain.value = ""
        self.plan_dropdown.value = None
        
        self.app.page.dialog = self.create_dialog
        self.create_dialog.open = True
        self.app.page.update()
    
    def _create_tenant(self):
        """Create a new tenant."""
        name = self.new_tenant_name.value.strip()
        plan_id = self.plan_dropdown.value
        domain = self.new_tenant_domain.value.strip() or None
        
        if not name:
            show_snackbar(self.app.page, "Tenant name is required", error=True)
            return
        
        if not plan_id:
            show_snackbar(self.app.page, "Please select a subscription plan", error=True)
            return
        
        result = api_client.create_tenant(name, plan_id, domain)
        
        if result and not result.get("error"):
            show_snackbar(self.app.page, f"Tenant '{name}' created successfully")
            self._load_tenants()
        else:
            error_msg = result.get("detail", "Failed to create tenant") if result else "Failed to create tenant"
            show_snackbar(self.app.page, error_msg, error=True)
    
    def _open_branding_dialog(self, tenant_id: str):
        """Open branding dialog for a tenant."""
        self.branding_tenant_id = tenant_id
        
        # Load existing settings
        settings = api_client.get_tenant_settings(tenant_id)
        if settings:
            self.branding_logo_url.value = settings.get("logo_url", "")
            self.branding_company_name.value = settings.get("company_name", "")
            self.branding_primary_color.value = settings.get("primary_color", "#6366f1")
            self.branding_secondary_color.value = settings.get("secondary_color", "#8b5cf6")
        
        self.app.page.dialog = self.branding_dialog
        self.branding_dialog.open = True
        self.app.page.update()
    
    def _save_branding(self):
        """Save tenant branding."""
        if not self.branding_tenant_id:
            return
        
        branding = {
            "logo_url": self.branding_logo_url.value or None,
            "company_name": self.branding_company_name.value or None,
            "primary_color": self.branding_primary_color.value,
            "secondary_color": self.branding_secondary_color.value,
        }
        
        result = api_client.set_tenant_branding(self.branding_tenant_id, branding)
        
        if result and not result.get("error"):
            show_snackbar(self.app.page, "Branding updated successfully")
            self.branding_tenant_id = None
        else:
            show_snackbar(self.app.page, "Failed to update branding", error=True)
    
    def _open_suspend_dialog(self, tenant_id: str):
        """Open suspend confirmation dialog."""
        self.suspend_tenant_id = tenant_id
        self.suspend_reason.value = ""
        
        self.app.page.dialog = self.suspend_dialog
        self.suspend_dialog.open = True
        self.app.page.update()
    
    def _confirm_suspend(self):
        """Confirm tenant suspension."""
        if not self.suspend_tenant_id:
            return
        
        reason = self.suspend_reason.value.strip()
        if len(reason) < 10:
            show_snackbar(self.app.page, "Please provide a reason (at least 10 characters)", error=True)
            return
        
        result = api_client.suspend_tenant(self.suspend_tenant_id, reason)
        
        if result and not result.get("error"):
            show_snackbar(self.app.page, "Tenant suspended")
            self.suspend_tenant_id = None
            self._load_tenants()
        else:
            show_snackbar(self.app.page, "Failed to suspend tenant", error=True)
    
    def _reactivate_tenant(self, tenant_id: str):
        """Reactivate a suspended tenant."""
        result = api_client.reactivate_tenant(tenant_id)
        
        if result and not result.get("error"):
            show_snackbar(self.app.page, "Tenant reactivated")
            self._load_tenants()
        else:
            show_snackbar(self.app.page, "Failed to reactivate tenant", error=True)
    
    def _view_settings(self, tenant_id: str):
        """View tenant settings."""
        settings = api_client.get_tenant_settings(tenant_id)
        
        if settings:
            content = ft.Column(
                [
                    ft.Text("Company Info", weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text(f"Name: {settings.get('company_name', 'Not set')}", color="grey"),
                    ft.Text(f"Currency: {settings.get('currency_code', 'USD')}", color="grey"),
                    ft.Divider(color="#3d4043"),
                    ft.Text("Branding", weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text(f"Primary Color: {settings.get('primary_color', 'Not set')}", color="grey"),
                    ft.Text(f"Logo: {'Set' if settings.get('logo_url') else 'Not set'}", color="grey"),
                    ft.Divider(color="#3d4043"),
                    ft.Text("Tax", weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text(f"Default Rate: {float(settings.get('default_tax_rate', 0)) * 100:.2f}%", color="grey"),
                ],
                scroll=ft.ScrollMode.AUTO,
            )
            
            dialog = ft.AlertDialog(
                title=ft.Text("Tenant Settings"),
                content=ft.Container(content=content, width=350, height=300),
                actions=[
                    ft.TextButton("Close", on_click=lambda e: self._close_dialog(dialog)),
                ],
            )
            
            self.app.page.dialog = dialog
            dialog.open = True
            self.app.page.update()
        else:
            show_snackbar(self.app.page, "No settings found for this tenant", error=True)
    
    def _close_dialog(self, dialog):
        """Close a dialog."""
        dialog.open = False
        self.app.page.update()
