"""Subscription Plans management view."""
import flet as ft

from config import config
from services.api_v2 import api_client
from components.dialogs import ConfirmDialog, FormDialog, show_snackbar


class PlansView(ft.Container):
    """Subscription plans management view."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        
        self._plans = []
        self._build()
    
    def _build(self):
        """Build the plans view layout."""
        # Action bar
        action_bar = ft.Row(
            [
                ft.Text(
                    "Manage subscription tiers for your tenants",
                    color="grey",
                ),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    icon_color="white",
                    tooltip="Refresh",
                    on_click=lambda e: self._load_plans(),
                ),
                ft.ElevatedButton(
                    "Create Plan",
                    icon=ft.Icons.ADD,
                    bgcolor=config.PRIMARY_COLOR,
                    color="white",
                    on_click=self._open_create_dialog,
                ),
            ],
        )
        
        # Plans container
        self.plans_container = ft.Row(
            wrap=True,
            spacing=20,
            run_spacing=20,
        )
        
        self.content = ft.Column(
            [
                action_bar,
                ft.Container(height=20),
                self.plans_container,
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        self._create_dialogs()
    
    def _create_dialogs(self):
        """Create dialog components."""
        # Create plan dialog
        self.plan_name = ft.TextField(label="Plan Name", data="name")
        self.plan_description = ft.TextField(
            label="Description",
            multiline=True,
            min_lines=2,
            data="description",
        )
        self.plan_price_monthly = ft.TextField(
            label="Monthly Price ($)",
            keyboard_type=ft.KeyboardType.NUMBER,
            data="price_monthly",
        )
        self.plan_price_annual = ft.TextField(
            label="Annual Price ($)",
            keyboard_type=ft.KeyboardType.NUMBER,
            data="price_annual",
        )
        self.plan_max_users = ft.TextField(
            label="Max Users",
            value="5",
            keyboard_type=ft.KeyboardType.NUMBER,
            data="max_users",
        )
        self.plan_max_products = ft.TextField(
            label="Max Products",
            value="1000",
            keyboard_type=ft.KeyboardType.NUMBER,
            data="max_products",
        )
        self.plan_max_locations = ft.TextField(
            label="Max Locations",
            value="1",
            keyboard_type=ft.KeyboardType.NUMBER,
            data="max_locations",
        )
        self.plan_features = ft.TextField(
            label="Features (comma-separated)",
            hint_text="e.g., inventory,reports,analytics",
            data="features",
        )
        
        self.create_dialog = FormDialog(
            title="Create Subscription Plan",
            fields=[
                self.plan_name,
                self.plan_description,
                ft.Row([self.plan_price_monthly, self.plan_price_annual], spacing=10),
                ft.Row([self.plan_max_users, self.plan_max_products, self.plan_max_locations], spacing=10),
                self.plan_features,
            ],
            on_submit=self._create_plan,
            width=500,
            height=400,
        )
    
    def did_mount(self):
        """Load data on mount."""
        self._load_plans()
    
    def _load_plans(self):
        """Load subscription plans."""
        self._plans = api_client.get_subscription_plans()
        self._render_plans()
    
    def _render_plans(self):
        """Render plan cards."""
        self.plans_container.controls = []
        
        if not self._plans:
            self.plans_container.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.CARD_MEMBERSHIP, size=64, color="grey"),
                            ft.Text("No subscription plans defined", size=16, color="grey"),
                            ft.Text("Create your first plan to get started", size=13, color="grey"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                    ),
                    expand=True,
                    alignment=ft.alignment.center,
                    padding=50,
                )
            )
        else:
            for plan in self._plans:
                self.plans_container.controls.append(self._build_plan_card(plan))
        
        self.update()
    
    def _build_plan_card(self, plan: dict) -> ft.Container:
        """Build a plan card."""
        plan_id = plan.get("id")
        name = plan.get("name", "Unknown")
        description = plan.get("description", "")
        price_monthly = plan.get("price_monthly", plan.get("price", 0))
        price_annual = plan.get("price_annual")
        max_users = plan.get("max_users", "∞")
        max_products = plan.get("max_products", "∞")
        max_locations = plan.get("max_locations", "∞")
        features = plan.get("features", [])
        is_active = plan.get("is_active", True)
        
        # Feature list
        feature_chips = []
        for feature in (features or [])[:5]:
            feature_chips.append(
                ft.Container(
                    content=ft.Text(feature, size=10, color="white"),
                    bgcolor=f"{config.PRIMARY_COLOR}40",
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    border_radius=12,
                )
            )
        
        return ft.Container(
            content=ft.Column(
                [
                    # Header
                    ft.Row(
                        [
                            ft.Text(
                                name,
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                color="white",
                            ),
                            ft.Container(expand=True),
                            ft.Container(
                                content=ft.Text(
                                    "Active" if is_active else "Inactive",
                                    size=10,
                                    color="white",
                                ),
                                bgcolor=config.SUCCESS_COLOR if is_active else "grey",
                                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                border_radius=10,
                            ),
                        ],
                    ),
                    
                    # Description
                    ft.Text(
                        description or "No description",
                        size=12,
                        color="grey",
                        max_lines=2,
                    ),
                    
                    ft.Container(height=10),
                    
                    # Price
                    ft.Row(
                        [
                            ft.Text("$", size=20, color=config.SUCCESS_COLOR),
                            ft.Text(
                                f"{float(price_monthly):.2f}",
                                size=36,
                                weight=ft.FontWeight.BOLD,
                                color=config.SUCCESS_COLOR,
                            ),
                            ft.Text("/mo", size=14, color="grey"),
                        ],
                        spacing=2,
                    ),
                    
                    ft.Text(
                        f"${float(price_annual):.2f}/year" if price_annual else "No annual pricing",
                        size=12,
                        color="grey",
                    ),
                    
                    ft.Divider(color="#3d4043"),
                    
                    # Limits
                    ft.Column(
                        [
                            self._build_limit_row(ft.Icons.PEOPLE, f"{max_users} users"),
                            self._build_limit_row(ft.Icons.INVENTORY_2, f"{max_products} products"),
                            self._build_limit_row(ft.Icons.LOCATION_ON, f"{max_locations} locations"),
                        ],
                        spacing=8,
                    ),
                    
                    ft.Container(height=10),
                    
                    # Features
                    ft.Row(
                        feature_chips,
                        wrap=True,
                        spacing=5,
                        run_spacing=5,
                    ) if feature_chips else ft.Text("No features defined", size=11, color="grey"),
                    
                    ft.Container(expand=True),
                    
                    # Actions
                    ft.Row(
                        [
                            ft.TextButton(
                                "Delete",
                                icon=ft.Icons.DELETE,
                                icon_color=config.ERROR_COLOR,
                                style=ft.ButtonStyle(color=config.ERROR_COLOR),
                                on_click=lambda e, pid=plan_id, pname=name: self._confirm_delete(pid, pname),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=5,
            ),
            width=300,
            height=400,
            bgcolor=config.SURFACE_COLOR,
            border_radius=12,
            padding=20,
            border=ft.border.all(1, "#3d4043"),
        )
    
    def _build_limit_row(self, icon: str, text: str) -> ft.Row:
        """Build a limit display row."""
        return ft.Row(
            [
                ft.Icon(icon, size=18, color="grey"),
                ft.Text(text, size=13, color="white"),
            ],
            spacing=10,
        )
    
    def _open_create_dialog(self, e):
        """Open create plan dialog."""
        # Reset fields
        self.plan_name.value = ""
        self.plan_description.value = ""
        self.plan_price_monthly.value = ""
        self.plan_price_annual.value = ""
        self.plan_max_users.value = "5"
        self.plan_max_products.value = "1000"
        self.plan_max_locations.value = "1"
        self.plan_features.value = ""
        
        self.app.page.dialog = self.create_dialog
        self.create_dialog.open = True
        self.app.page.update()
    
    def _create_plan(self):
        """Create a new subscription plan."""
        name = self.plan_name.value.strip()
        
        if not name:
            show_snackbar(self.app.page, "Plan name is required", error=True)
            return
        
        try:
            price_monthly = float(self.plan_price_monthly.value or 0)
        except ValueError:
            show_snackbar(self.app.page, "Invalid monthly price", error=True)
            return
        
        try:
            price_annual = float(self.plan_price_annual.value) if self.plan_price_annual.value else None
        except ValueError:
            show_snackbar(self.app.page, "Invalid annual price", error=True)
            return
        
        features = [
            f.strip() for f in (self.plan_features.value or "").split(",")
            if f.strip()
        ]
        
        plan_data = {
            "name": name,
            "description": self.plan_description.value or None,
            "price_monthly": price_monthly,
            "price_annual": price_annual,
            "max_users": int(self.plan_max_users.value or 5),
            "max_products": int(self.plan_max_products.value or 1000),
            "max_locations": int(self.plan_max_locations.value or 1),
            "features": features,
            "is_active": True,
        }
        
        result = api_client.create_subscription_plan(plan_data)
        
        if result and not result.get("error"):
            show_snackbar(self.app.page, f"Plan '{name}' created successfully")
            self._load_plans()
        else:
            error_msg = result.get("detail", "Failed to create plan") if result else "Failed to create plan"
            show_snackbar(self.app.page, error_msg, error=True)
    
    def _confirm_delete(self, plan_id: str, plan_name: str):
        """Show delete confirmation dialog."""
        dialog = ConfirmDialog(
            title="Delete Plan",
            message=f"Are you sure you want to delete '{plan_name}'?\n\nNote: This will fail if any tenants are using this plan.",
            confirm_text="Delete",
            on_confirm=lambda: self._delete_plan(plan_id),
            danger=True,
        )
        
        self.app.page.dialog = dialog
        dialog.open = True
        self.app.page.update()
    
    def _delete_plan(self, plan_id: str):
        """Delete a subscription plan."""
        result = api_client.delete_subscription_plan(plan_id)
        
        if result and not result.get("error"):
            show_snackbar(self.app.page, "Plan deleted successfully")
            self._load_plans()
        else:
            error_msg = result.get("detail", "Failed to delete plan") if result else "Failed to delete plan"
            show_snackbar(self.app.page, error_msg, error=True)
