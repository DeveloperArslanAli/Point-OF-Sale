import json
from pathlib import Path

import flet as ft
import jwt

from views.login import LoginView
from views.dashboard import DashboardView
from views.pos import POSView
from views.orders import OrdersView
from views.inventory import InventoryView
from views.intelligence import IntelligenceView
from views.customers import CustomersView
from views.employees import EmployeesView
from views.users import UsersView
from views.returns import ReturnsView
from views.settings import SettingsView
from views.promotions import PromotionsView
from components.sidebar import Sidebar
from services.api import api_service

class ModernPOSApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.setup_page()
        self._setup_error_handling()
        self.token = None
        self.user_role = None
        self.current_view = None
        self.current_route = None
        self.main_layout = None
        self.content_area = None
        self.token_store = Path(__file__).parent / ".auth_tokens.json"
        if not self._restore_session():
            self.navigate("login")

    def _setup_error_handling(self):
        def on_error(message):
            try:
                self.page.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Text(message, color="white"),
                        bgcolor="#cf6679",
                        action="Dismiss",
                        action_color="white"
                    )
                )
            except Exception as exc:
                # Fallback to console logging if the UI is not ready yet (e.g., during session restore)
                print(f"UI error display failed: {exc}; original error: {message}")
        api_service.set_error_handler(on_error)

    def setup_page(self):
        self.page.title = "Retail POS - Modern"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 0
        self.page.bgcolor = "#1a1c1e"
        self.page.fonts = {
            "Roboto": "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf",
            "RobotoBold": "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
        }
        self.page.theme = ft.Theme(font_family="Roboto")

    def login(self, token):
        self.token = token
        try:
            # Decode token without verification (backend verifies) to get role
            decoded = jwt.decode(token, options={"verify_signature": False})
            self.user_role = decoded.get("role", "CASHIER") # Default to restricted if missing
            print(f"User logged in with role: {self.user_role}")
        except Exception as e:
            print(f"Error decoding token: {e}")
            self.user_role = "CASHIER"

        self._persist_tokens()

        if self.user_role == "CASHIER":
            self.navigate("pos")
        else:
            self.navigate("dashboard")

    def logout(self):
        try:
            api_service.logout()
        except Exception:
            pass
        self.token = None
        self.user_role = None
        self.current_route = None
        self.main_layout = None
        self.content_area = None
        self._clear_tokens()
        self.navigate("login")

    def navigate(self, route):
        # Prevent redundant navigation
        if self.current_route == route:
            return
            
        # Role Guard: Cashiers can only access POS, Login, Logout
        if self.user_role == "CASHIER" and route not in ["pos", "login", "logout"]:
            print(f"Access denied: Cashier attempted to access {route}")
            return

        self.current_route = route
        
        if route == "login":
            self.page.controls.clear()
            self.current_view = LoginView(self)
            self.page.add(self.current_view)
            self.page.update()
            return
            
        if route == "logout":
            self.logout()
            return

        # Authenticated Routes
        if not self.token:
            self.current_route = None
            self.navigate("login")
            return

        # Create Main Layout if it doesn't exist
        if not self.main_layout:
            self.content_area = ft.Container(expand=True, bgcolor="#1a1c1e")
            
            if self.user_role == "CASHIER":
                # Cashier Layout: Full Screen POS, No Sidebar
                self.main_layout = self.content_area
            else:
                # Standard Layout: Sidebar + Content
                self.main_layout = ft.Row(
                    [
                        Sidebar(self, self.page),
                        ft.VerticalDivider(width=1, color="#2d3033"),
                        self.content_area
                    ],
                    expand=True,
                    spacing=0
                )

        # Select View
        if route == "dashboard":
            content = DashboardView(self)
        elif route == "pos":
            content = POSView(self)
        elif route == "orders":
            content = OrdersView(self)
        elif route == "inventory":
            content = InventoryView(self)
        elif route == "intelligence":
            content = IntelligenceView(self)
        elif route == "customers":
            content = CustomersView(self)
        elif route == "employees":
            content = EmployeesView(self)
        elif route == "users":
            content = UsersView(self)
        elif route == "returns":
            content = ReturnsView(self)
        elif route == "settings":
            content = SettingsView(self)
        elif route == "promotions":
            content = PromotionsView(self)
        else:
            content = ft.Container(alignment=ft.alignment.center, content=ft.Text(f"{route.capitalize()} Coming Soon", size=30))

        # Update Content
        self.content_area.content = content
        
        # Ensure Main Layout is displayed
        if self.main_layout not in self.page.controls:
            self.page.controls.clear()
            self.page.add(self.main_layout)
        
        self.page.update()

    def _persist_tokens(self):
        if not self.token:
            return
        data = {
            "access_token": self.token,
            "refresh_token": api_service.refresh_token,
        }
        try:
            self.token_store.write_text(json.dumps(data))
        except Exception as exc:
            print(f"Warning: failed to persist tokens: {exc}")

    def _clear_tokens(self):
        try:
            if self.token_store.exists():
                self.token_store.unlink()
        except Exception as exc:
            print(f"Warning: failed to clear tokens: {exc}")

    def _restore_session(self) -> bool:
        if not self.token_store.exists():
            return False
        try:
            data = json.loads(self.token_store.read_text())
            access = data.get("access_token")
            refresh = data.get("refresh_token")
            if not access:
                return False
            api_service.set_tokens(access, refresh)
            me = api_service.me()
            if me and me.get("role"):
                self.token = access
                self.user_role = me.get("role")
                self.navigate("pos" if self.user_role == "CASHIER" else "dashboard")
                return True
        except Exception as exc:
            print(f"Session restore failed: {exc}")
        self._clear_tokens()
        return False

def main(page: ft.Page):
    app = ModernPOSApp(page)

if __name__ == "__main__":
    try:
        # Run on port 8080 as requested
        ft.app(target=main, port=8080)
    except Exception as e:
        print(f"Error starting app: {e}")
