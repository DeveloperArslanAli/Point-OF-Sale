"""Super Admin Portal - Main Application.

Production-ready enterprise multi-tenant management portal.
"""
print("Starting SuperAdmin Portal...")

import flet as ft

from config import config
from services.api_v2 import api_client
from components.sidebar import Sidebar


class SuperAdminApp:
    """Main application controller."""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self._setup_page()
        self._current_route = "login"
        self._current_view = None
        
        # Check for existing authentication
        if api_client.is_authenticated() and api_client.is_super_admin():
            self._current_route = "dashboard"
            self._build_main_layout()
        else:
            self._show_login()
    
    def _setup_page(self):
        """Configure page settings."""
        self.page.title = config.APP_TITLE
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = config.BACKGROUND_COLOR
        self.page.padding = 0
        self.page.spacing = 0
        
        # Responsive
        self.page.on_resize = self._on_resize
    
    def _on_resize(self, e):
        """Handle window resize."""
        pass  # Can implement responsive behavior here
    
    def _show_login(self):
        """Show login view."""
        from views.login_v2 import LoginView
        
        self.page.controls.clear()
        login_view = LoginView(on_login_success=self._on_login_success)
        self.page.add(login_view)
        self.page.update()
    
    def _on_login_success(self):
        """Handle successful login."""
        if api_client.is_super_admin():
            self._current_route = "dashboard"
            self._build_main_layout()
        else:
            # Not a super admin - show error and logout
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("Access denied. Super Admin role required."),
                bgcolor=config.ERROR_COLOR,
            )
            self.page.snack_bar.open = True
            api_client.logout()
            self.page.update()
    
    def _build_main_layout(self):
        """Build the main application layout with sidebar."""
        self.page.controls.clear()
        
        # Create sidebar
        self.sidebar = Sidebar(
            on_navigate=self._navigate,
            selected_route=self._current_route,
        )
        
        # Content area
        self.content_area = ft.Container(
            expand=True,
            padding=20,
            bgcolor=config.BACKGROUND_COLOR,
        )
        
        # Top bar
        user_info = api_client.get_current_user()
        user_email = user_info.get("email", "Super Admin") if user_info else "Super Admin"
        
        self.topbar = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        self._get_page_title(self._current_route),
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color="white",
                    ),
                    ft.Container(expand=True),
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.ACCOUNT_CIRCLE, color="grey"),
                            ft.Text(user_email, color="grey", size=13),
                            ft.PopupMenuButton(
                                icon=ft.Icons.MORE_VERT,
                                icon_color="grey",
                                items=[
                                    ft.PopupMenuItem(
                                        text="Settings",
                                        icon=ft.Icons.SETTINGS,
                                        on_click=lambda e: self._navigate("settings"),
                                    ),
                                    ft.PopupMenuItem(
                                        text="Logout",
                                        icon=ft.Icons.LOGOUT,
                                        on_click=self._logout,
                                    ),
                                ],
                            ),
                        ],
                        spacing=10,
                    ),
                ],
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=15),
            bgcolor=config.SURFACE_COLOR,
        )
        
        # Main layout
        main_row = ft.Row(
            [
                self.sidebar,
                ft.Column(
                    [
                        self.topbar,
                        self.content_area,
                    ],
                    expand=True,
                    spacing=0,
                ),
            ],
            expand=True,
            spacing=0,
        )
        
        self.page.add(main_row)
        
        # Load initial view
        self._load_view(self._current_route)
        self.page.update()
    
    def _get_page_title(self, route: str) -> str:
        """Get page title for route."""
        titles = {
            "dashboard": "Dashboard",
            "tenants": "Tenant Management",
            "plans": "Subscription Plans",
            "billing": "Billing & Revenue",
            "monitoring": "System Monitoring",
            "compliance": "Compliance",
            "analytics": "Analytics",
            "reports": "Reports",
            "integrations": "Integrations",
            "settings": "Settings",
        }
        return titles.get(route, route.title())
    
    def _navigate(self, route: str):
        """Navigate to a route."""
        self._current_route = route
        
        # Update topbar title
        if hasattr(self, "topbar"):
            title_text = self.topbar.content.controls[0]
            if isinstance(title_text, ft.Text):
                title_text.value = self._get_page_title(route)
        
        # Update sidebar selection
        if hasattr(self, "sidebar"):
            self.sidebar.set_selected(route)
        
        # Load view
        self._load_view(route)
        self.page.update()
    
    def _load_view(self, route: str):
        """Load the view for a route."""
        view = None
        
        try:
            if route == "dashboard":
                from views.dashboard_v2 import DashboardView
                view = DashboardView(app=self)
            elif route == "tenants":
                from views.tenants import TenantsView
                view = TenantsView(app=self)
            elif route == "plans":
                from views.plans import PlansView
                view = PlansView(app=self)
            elif route == "monitoring":
                from views.monitoring import MonitoringView
                view = MonitoringView(app=self)
            elif route == "compliance":
                from views.compliance import ComplianceView
                view = ComplianceView(app=self)
            elif route == "analytics":
                from views.analytics import AnalyticsView
                view = AnalyticsView(app=self)
            elif route == "integrations":
                from views.integrations import IntegrationsView
                view = IntegrationsView(app=self)
            elif route == "settings":
                from views.settings import SettingsView
                view = SettingsView(app=self)
            else:
                # Placeholder for unimplemented views
                view = self._build_placeholder_view(route)
        except ImportError as e:
            print(f"View import error for {route}: {e}")
            view = self._build_placeholder_view(route)
        
        self._current_view = view
        self.content_area.content = view
    
    def _build_placeholder_view(self, route: str) -> ft.Container:
        """Build a placeholder for unimplemented views."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.CONSTRUCTION, size=64, color="grey"),
                    ft.Text(
                        f"{route.title()} View",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color="white",
                    ),
                    ft.Text(
                        "This section is under development.",
                        color="grey",
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=15,
            ),
            expand=True,
            alignment=ft.alignment.center,
        )
    
    def _logout(self, e):
        """Handle logout."""
        api_client.logout()
        self._show_login()
    
    def show_snackbar(self, message: str, error: bool = False):
        """Show a snackbar notification."""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color="white"),
            bgcolor=config.ERROR_COLOR if error else config.SUCCESS_COLOR,
        )
        self.page.snack_bar.open = True
        self.page.update()


def main(page: ft.Page):
    """Application entry point."""
    SuperAdminApp(page)


if __name__ == "__main__":
    try:
        ft.app(
            target=main,
            port=config.APP_PORT,
            view=ft.AppView.WEB_BROWSER,
        )
    except Exception as e:
        print(f"Error starting app: {e}")
        import traceback
        traceback.print_exc()
