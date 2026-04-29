import flet as ft
from services.api import api_client

class LoginView(ft.Container):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.alignment = ft.alignment.center
        
        self.email = ft.TextField(label="Email", width=300)
        self.password = ft.TextField(label="Password", password=True, width=300)
        self.error_text = ft.Text(color="red")
        
        self.content = ft.Column(
            [
                ft.Text("SuperAdmin Portal", size=30, weight="bold"),
                self.email,
                self.password,
                self.error_text,
                ft.ElevatedButton("Login", on_click=self._login)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

    def _login(self, e):
        self.error_text.value = ""
        self.update()
        
        res = api_client.login(self.email.value, self.password.value)
        
        if res and "access_token" in res:
            token = res["access_token"]
            api_client.set_token(token)
            self.app.login(token)
        else:
            self.error_text.value = "Login failed. Check credentials or server connection."
            self.update()
