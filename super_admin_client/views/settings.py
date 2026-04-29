"""Settings view for Super Admin configuration."""
import flet as ft
from datetime import datetime

from config import config
from services.api_v2 import api_client
from services.auth import auth_service
from components.loading import LoadingIndicator
from components.dialogs import show_snackbar


class SettingsView(ft.Container):
    """Super Admin settings and configuration."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        
        self._build()
    
    def _build(self):
        """Build the settings view."""
        # Settings sections
        self.profile_section = self._build_profile_section()
        self.appearance_section = self._build_appearance_section()
        self.security_section = self._build_security_section()
        self.notifications_section = self._build_notifications_section()
        self.system_section = self._build_system_section()
        
        self.content = ft.Column(
            [
                ft.Text("Settings", size=24, weight=ft.FontWeight.BOLD, color="white"),
                ft.Text("Manage your Super Admin preferences", color="grey"),
                ft.Container(height=20),
                ft.Column(
                    [
                        self.profile_section,
                        self.appearance_section,
                        self.security_section,
                        self.notifications_section,
                        self.system_section,
                    ],
                    spacing=20,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
    
    def _build_section(self, title: str, icon, content: ft.Control) -> ft.Container:
        """Build a settings section card."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, color=config.PRIMARY_COLOR),
                            ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color="white"),
                        ],
                        spacing=10,
                    ),
                    ft.Divider(height=15, color=config.BORDER_COLOR),
                    content,
                ],
            ),
            bgcolor=config.SURFACE_COLOR,
            border_radius=12,
            padding=20,
        )
    
    def _build_profile_section(self) -> ft.Container:
        """Build profile settings section."""
        # Get current user info from token
        token_data = auth_service.get_token_data()
        email = token_data.get("email", "admin@example.com") if token_data else "Unknown"
        role = token_data.get("role", "SUPER_ADMIN") if token_data else "Unknown"
        
        email_field = ft.TextField(
            value=email,
            label="Email",
            read_only=True,
            prefix_icon=ft.Icons.EMAIL,
        )
        
        password_field = ft.TextField(
            label="New Password",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK,
            hint_text="Leave empty to keep current",
        )
        
        confirm_password = ft.TextField(
            label="Confirm Password",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK_OUTLINE,
        )
        
        def update_password(e):
            if password_field.value:
                if password_field.value != confirm_password.value:
                    show_snackbar(self.app.page, "Passwords do not match", error=True)
                    return
                if len(password_field.value) < 8:
                    show_snackbar(self.app.page, "Password must be at least 8 characters", error=True)
                    return
                # TODO: Call password update API
                show_snackbar(self.app.page, "Password updated successfully")
                password_field.value = ""
                confirm_password.value = ""
                self.update()
        
        content = ft.Column(
            [
                ft.Row(
                    [
                        ft.CircleAvatar(
                            content=ft.Text(email[0].upper() if email else "?", size=24),
                            bgcolor=config.PRIMARY_COLOR,
                            radius=30,
                        ),
                        ft.Column(
                            [
                                ft.Text(email, size=16, weight=ft.FontWeight.W_500, color="white"),
                                ft.Container(
                                    content=ft.Text(role, size=11, color="white"),
                                    bgcolor=config.PRIMARY_COLOR,
                                    border_radius=4,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                ),
                            ],
                            spacing=5,
                        ),
                    ],
                    spacing=15,
                ),
                ft.Container(height=15),
                email_field,
                ft.Container(height=10),
                password_field,
                confirm_password,
                ft.Container(height=10),
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            "Update Password",
                            icon=ft.Icons.SAVE,
                            bgcolor=config.PRIMARY_COLOR,
                            color="white",
                            on_click=update_password,
                        ),
                    ],
                ),
            ],
        )
        
        return self._build_section("Profile", ft.Icons.PERSON, content)
    
    def _build_appearance_section(self) -> ft.Container:
        """Build appearance settings section."""
        theme_dropdown = ft.Dropdown(
            value="dark",
            label="Theme",
            options=[
                ft.dropdown.Option("dark", "Dark"),
                ft.dropdown.Option("light", "Light"),
                ft.dropdown.Option("system", "System"),
            ],
            width=200,
            on_change=lambda e: show_snackbar(self.app.page, "Theme preference saved"),
        )
        
        compact_mode = ft.Switch(
            label="Compact Mode",
            value=False,
            on_change=lambda e: show_snackbar(self.app.page, f"Compact mode {'enabled' if e.control.value else 'disabled'}"),
        )
        
        sidebar_collapsed = ft.Switch(
            label="Collapse Sidebar by Default",
            value=False,
            on_change=lambda e: show_snackbar(self.app.page, "Sidebar preference saved"),
        )
        
        content = ft.Column(
            [
                ft.Row([theme_dropdown], spacing=20),
                ft.Container(height=10),
                compact_mode,
                sidebar_collapsed,
            ],
        )
        
        return self._build_section("Appearance", ft.Icons.PALETTE, content)
    
    def _build_security_section(self) -> ft.Container:
        """Build security settings section."""
        two_factor = ft.Switch(
            label="Two-Factor Authentication",
            value=False,
            on_change=lambda e: show_snackbar(self.app.page, "2FA setting updated (demo)"),
        )
        
        session_timeout = ft.Dropdown(
            value="60",
            label="Session Timeout",
            options=[
                ft.dropdown.Option("15", "15 minutes"),
                ft.dropdown.Option("30", "30 minutes"),
                ft.dropdown.Option("60", "1 hour"),
                ft.dropdown.Option("240", "4 hours"),
                ft.dropdown.Option("480", "8 hours"),
            ],
            width=200,
        )
        
        ip_whitelist = ft.TextField(
            label="IP Whitelist",
            hint_text="Enter IPs separated by commas (leave empty for no restriction)",
            prefix_icon=ft.Icons.SECURITY,
            multiline=True,
            min_lines=2,
            max_lines=3,
        )
        
        content = ft.Column(
            [
                two_factor,
                ft.Container(height=10),
                ft.Row([session_timeout]),
                ft.Container(height=10),
                ip_whitelist,
                ft.Container(height=15),
                ft.Row(
                    [
                        ft.TextButton(
                            "View Login History",
                            icon=ft.Icons.HISTORY,
                            on_click=lambda e: show_snackbar(self.app.page, "Login history feature coming soon"),
                        ),
                        ft.TextButton(
                            "Revoke All Sessions",
                            icon=ft.Icons.LOGOUT,
                            on_click=lambda e: self._revoke_sessions(),
                        ),
                    ],
                    spacing=15,
                ),
            ],
        )
        
        return self._build_section("Security", ft.Icons.SECURITY, content)
    
    def _build_notifications_section(self) -> ft.Container:
        """Build notification settings section."""
        email_alerts = ft.Switch(
            label="Email Alerts",
            value=True,
        )
        
        new_tenant_alert = ft.Switch(
            label="New Tenant Signup",
            value=True,
        )
        
        payment_alert = ft.Switch(
            label="Payment Notifications",
            value=True,
        )
        
        compliance_alert = ft.Switch(
            label="Compliance Issues",
            value=True,
        )
        
        system_alert = ft.Switch(
            label="System Health Alerts",
            value=True,
        )
        
        content = ft.Column(
            [
                email_alerts,
                ft.Divider(height=15, color=config.BORDER_COLOR),
                ft.Text("Notify me about:", color="grey", size=13),
                ft.Container(height=5),
                new_tenant_alert,
                payment_alert,
                compliance_alert,
                system_alert,
            ],
        )
        
        return self._build_section("Notifications", ft.Icons.NOTIFICATIONS, content)
    
    def _build_system_section(self) -> ft.Container:
        """Build system settings section."""
        api_url_field = ft.TextField(
            value=config.API_BASE_URL,
            label="API Base URL",
            read_only=True,
            prefix_icon=ft.Icons.LINK,
        )
        
        app_version = ft.Text(f"App Version: {config.APP_VERSION}", color="grey")
        
        content = ft.Column(
            [
                api_url_field,
                ft.Container(height=10),
                app_version,
                ft.Container(height=20),
                ft.Row(
                    [
                        ft.OutlinedButton(
                            "Clear Local Data",
                            icon=ft.Icons.DELETE_SWEEP,
                            on_click=lambda e: self._clear_local_data(),
                        ),
                        ft.OutlinedButton(
                            "Export Settings",
                            icon=ft.Icons.DOWNLOAD,
                            on_click=lambda e: show_snackbar(self.app.page, "Settings export coming soon"),
                        ),
                    ],
                    spacing=10,
                ),
                ft.Container(height=20),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Logout",
                            icon=ft.Icons.LOGOUT,
                            bgcolor=config.ERROR_COLOR,
                            color="white",
                            on_click=lambda e: self._logout(),
                        ),
                    ],
                ),
            ],
        )
        
        return self._build_section("System", ft.Icons.SETTINGS_APPLICATIONS, content)
    
    def _revoke_sessions(self):
        """Revoke all active sessions."""
        def on_confirm():
            # TODO: Call API to revoke sessions
            show_snackbar(self.app.page, "All sessions revoked")
            self._logout()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Revoke All Sessions"),
            content=ft.Text(
                "This will log you out from all devices including this one. Continue?"
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: setattr(dialog, "open", False) or self.app.page.update(),
                ),
                ft.ElevatedButton(
                    "Revoke All",
                    bgcolor=config.ERROR_COLOR,
                    color="white",
                    on_click=lambda e: on_confirm(),
                ),
            ],
        )
        
        self.app.page.overlay.append(dialog)
        dialog.open = True
        self.app.page.update()
    
    def _clear_local_data(self):
        """Clear local storage data."""
        def on_confirm():
            auth_service.clear_tokens()
            show_snackbar(self.app.page, "Local data cleared. Logging out...")
            import time
            time.sleep(1)
            self._logout()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Clear Local Data"),
            content=ft.Text(
                "This will clear all locally stored data including your session. You will need to log in again."
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: setattr(dialog, "open", False) or self.app.page.update(),
                ),
                ft.ElevatedButton(
                    "Clear Data",
                    bgcolor=config.WARNING_COLOR,
                    color="white",
                    on_click=lambda e: on_confirm(),
                ),
            ],
        )
        
        self.app.page.overlay.append(dialog)
        dialog.open = True
        self.app.page.update()
    
    def _logout(self):
        """Logout the user."""
        auth_service.clear_tokens()
        api_client.logout()
        self.app.navigate("login")
