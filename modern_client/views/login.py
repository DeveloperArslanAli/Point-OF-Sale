import flet as ft
icons = ft.icons

class LoginView(ft.Container):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.alignment = ft.alignment.center
        self.image_src = "https://images.unsplash.com/photo-1556742049-0cfed4f7a07d?q=80&w=1920&auto=format&fit=crop"
        self.image_fit = ft.ImageFit.COVER
        self.image_opacity = 0.4
        self.content = self._build_login_card()

    def _build_login_card(self):
        self.email_field = ft.TextField(
            label="Email", width=300, bgcolor="#2d3033", border_color="#bb86fc", color="white", prefix_icon=icons.EMAIL
        )
        self.password_field = ft.TextField(
            label="Password", width=300, password=True, can_reveal_password=True, bgcolor="#2d3033", border_color="#bb86fc", color="white", prefix_icon=icons.LOCK
        )
        self.error_text = ft.Text("", color="#cf6679", size=12)

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Welcome Back", size=32, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text("Sign in to continue", size=16, color="grey"),
                    ft.Divider(height=20, color="transparent"),
                    self.email_field,
                    self.password_field,
                    self.error_text,
                    ft.Divider(height=20, color="transparent"),
                    ft.ElevatedButton(
                        "LOGIN", 
                        width=300, 
                        height=50, 
                        style=ft.ButtonStyle(bgcolor="#bb86fc", color="black", shape=ft.RoundedRectangleBorder(radius=10)),
                        on_click=self._login_click
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            width=400,
            height=500,
            bgcolor="#2d3033",
            border_radius=20,
            padding=40,
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=15, color="#80000000")
        )

    def _login_click(self, e):
        if not self.email_field.value or not self.password_field.value:
            self.error_text.value = "Please enter both email and password"
            self.error_text.update()
            return
        
        self.error_text.value = "Logging in..."
        self.error_text.update()

        # Real API Call
        from services.api import api_service
        result = api_service.login(self.email_field.value, self.password_field.value)
        
        if result and "access_token" in result:
            api_service.set_tokens(result.get("access_token"), result.get("refresh_token"))
            self.app.login(result["access_token"])
        else:
            self.error_text.value = "Login failed. Check credentials."
            self.error_text.update()
