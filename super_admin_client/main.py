print("Starting SuperAdmin Client...")
import flet as ft
from views.login import LoginView
from views.dashboard import DashboardView

class SuperAdminApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Retail POS - SuperAdmin Portal"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = "#1a1c1e"
        self.token = None
        self.navigate("login")

    def login(self, token):
        self.token = token
        self.navigate("dashboard")

    def navigate(self, route):
        self.page.controls.clear()
        if route == "login":
            self.page.add(LoginView(self))
        elif route == "dashboard":
            self.page.add(DashboardView(self))
        self.page.update()

def main(page: ft.Page):
    app = SuperAdminApp(page)

if __name__ == "__main__":
    try:
        ft.app(target=main, port=8081, view=ft.AppView.WEB_BROWSER) 
        # Running on port 8081 as requested, in web browser mode for "Portal" feel
    except Exception as e:
        print(f"Error starting app: {e}")
        import traceback
        traceback.print_exc()
