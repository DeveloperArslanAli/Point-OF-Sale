"""Login view for Super Admin Portal."""
from typing import Callable

import flet as ft

from config import config
from services.api_v2 import api_client


class LoginView(ft.Container):
    """Login form with validation and error handling."""
    
    def __init__(self, on_login_success: Callable[[], None]):
        super().__init__()
        self.on_login_success = on_login_success
        self.expand = True
        self.alignment = ft.alignment.center
        self.bgcolor = config.BACKGROUND_COLOR
        
        self._build()
    
    def _build(self):
        """Build the login form."""
        # Email field
        self.email_field = ft.TextField(
            label="Email",
            prefix_icon=ft.Icons.EMAIL,
            width=350,
            border_radius=8,
            focused_border_color=config.PRIMARY_COLOR,
            on_submit=self._handle_login,
        )
        
        # Password field
        self.password_field = ft.TextField(
            label="Password",
            prefix_icon=ft.Icons.LOCK,
            password=True,
            can_reveal_password=True,
            width=350,
            border_radius=8,
            focused_border_color=config.PRIMARY_COLOR,
            on_submit=self._handle_login,
        )
        
        # Error message
        self.error_text = ft.Text(
            "",
            color=config.ERROR_COLOR,
            size=13,
            visible=False,
        )
        
        # Login button
        self.login_button = ft.ElevatedButton(
            "Sign In",
            width=350,
            height=45,
            bgcolor=config.PRIMARY_COLOR,
            color="white",
            on_click=self._handle_login,
        )
        
        # Loading indicator
        self.loading = ft.ProgressRing(
            width=20,
            height=20,
            color=config.PRIMARY_COLOR,
            visible=False,
        )
        
        # Form card
        form_card = ft.Container(
            content=ft.Column(
                [
                    # Logo and title
                    ft.Icon(
                        ft.Icons.ADMIN_PANEL_SETTINGS,
                        size=64,
                        color=config.PRIMARY_COLOR,
                    ),
                    ft.Text(
                        "SuperAdmin Portal",
                        size=28,
                        weight=ft.FontWeight.BOLD,
                        color="white",
                    ),
                    ft.Text(
                        "Sign in to manage your POS platform",
                        size=14,
                        color="grey",
                    ),
                    ft.Container(height=20),
                    
                    # Form fields
                    self.email_field,
                    ft.Container(height=5),
                    self.password_field,
                    ft.Container(height=5),
                    self.error_text,
                    ft.Container(height=10),
                    
                    # Button row
                    ft.Stack(
                        [
                            self.login_button,
                            ft.Container(
                                content=self.loading,
                                alignment=ft.alignment.center,
                                width=350,
                                height=45,
                            ),
                        ],
                    ),
                    
                    ft.Container(height=20),
                    ft.Text(
                        "© 2024 Retail POS System",
                        size=11,
                        color="grey",
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5,
            ),
            padding=40,
            bgcolor=config.SURFACE_COLOR,
            border_radius=16,
            shadow=ft.BoxShadow(
                blur_radius=20,
                color="#00000044",
                offset=ft.Offset(0, 4),
            ),
        )
        
        self.content = form_card
    
    def _handle_login(self, e):
        """Handle login button click."""
        # Clear previous error
        self.error_text.visible = False
        
        # Validate fields
        email = self.email_field.value.strip() if self.email_field.value else ""
        password = self.password_field.value if self.password_field.value else ""
        
        if not email:
            self._show_error("Please enter your email")
            return
        
        if not password:
            self._show_error("Please enter your password")
            return
        
        if "@" not in email:
            self._show_error("Please enter a valid email address")
            return
        
        # Show loading state
        self._set_loading(True)
        
        # Attempt login
        result = api_client.login(email, password)
        
        self._set_loading(False)
        
        if result and "access_token" in result:
            # Verify super admin role
            if api_client.is_super_admin():
                self.on_login_success()
            else:
                api_client.logout()
                self._show_error("Access denied. Super Admin role required.")
        else:
            error_msg = "Login failed. Please check your credentials."
            if result and isinstance(result, dict):
                error_msg = result.get("detail", error_msg)
            self._show_error(error_msg)
    
    def _show_error(self, message: str):
        """Display error message."""
        self.error_text.value = message
        self.error_text.visible = True
        self.update()
    
    def _set_loading(self, loading: bool):
        """Toggle loading state."""
        self.loading.visible = loading
        self.login_button.disabled = loading
        self.login_button.opacity = 0.5 if loading else 1
        self.update()
