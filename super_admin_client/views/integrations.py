"""Integrations view for webhooks and API management."""
import flet as ft
from datetime import datetime

from config import config
from services.api_v2 import api_client
from components.badge import StatusBadge
from components.loading import LoadingIndicator
from components.dialogs import FormDialog, ConfirmDialog, show_snackbar


class IntegrationsView(ft.Container):
    """Webhooks and API integrations management."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        
        self._build()
    
    def _build(self):
        """Build the integrations view."""
        # Tabs
        self.tabs = ft.Tabs(
            selected_index=0,
            tabs=[
                ft.Tab(text="Webhooks", icon=ft.Icons.WEBHOOK),
                ft.Tab(text="API Endpoints", icon=ft.Icons.API),
            ],
            on_change=self._on_tab_change,
        )
        
        # Content containers
        self.webhooks_content = self._build_webhooks_section()
        self.api_content = self._build_api_section()
        
        self.content_area = ft.Container(
            content=self.webhooks_content,
            expand=True,
        )
        
        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Integrations & Webhooks", color="grey"),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            "Create Webhook",
                            icon=ft.Icons.ADD,
                            bgcolor=config.PRIMARY_COLOR,
                            color="white",
                            on_click=self._show_create_webhook_dialog,
                        ),
                    ],
                ),
                ft.Container(height=10),
                self.tabs,
                ft.Container(height=20),
                self.content_area,
            ],
            expand=True,
        )
    
    def _build_webhooks_section(self):
        """Build webhooks section."""
        self.webhooks_container = ft.Container(
            content=LoadingIndicator(message="Loading webhooks..."),
            expand=True,
        )
        return self.webhooks_container
    
    def _build_api_section(self):
        """Build API endpoints section."""
        self.api_container = ft.Container(
            content=LoadingIndicator(message="Loading API info..."),
            expand=True,
        )
        return self.api_container
    
    def _on_tab_change(self, e):
        """Handle tab change."""
        if e.control.selected_index == 0:
            self.content_area.content = self.webhooks_content
            self._load_webhooks()
        else:
            self.content_area.content = self.api_content
            self._load_api_info()
        self.update()
    
    def did_mount(self):
        """Load data on mount."""
        self._load_webhooks()
    
    def _load_webhooks(self):
        """Load webhook configurations."""
        webhooks = api_client.get_webhooks()
        
        if webhooks and not webhooks.get("error"):
            items = webhooks.get("items", webhooks if isinstance(webhooks, list) else [])
            
            if items:
                webhook_cards = []
                for wh in items:
                    webhook_cards.append(self._build_webhook_card(wh))
                
                self.webhooks_container.content = ft.Column(
                    [
                        # Stats row
                        ft.Row(
                            [
                                self._build_stat_box("Total Webhooks", len(items), ft.Icons.WEBHOOK),
                                self._build_stat_box(
                                    "Active",
                                    len([w for w in items if w.get("is_active", True)]),
                                    ft.Icons.CHECK_CIRCLE,
                                    color=config.SUCCESS_COLOR,
                                ),
                                self._build_stat_box(
                                    "Inactive",
                                    len([w for w in items if not w.get("is_active", True)]),
                                    ft.Icons.PAUSE_CIRCLE,
                                    color=config.WARNING_COLOR,
                                ),
                            ],
                            spacing=20,
                        ),
                        ft.Container(height=20),
                        ft.Text("Webhook Configurations", size=16, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Container(height=10),
                        ft.Column(webhook_cards, spacing=10),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                )
            else:
                self.webhooks_container.content = self._build_empty_webhooks()
        else:
            self.webhooks_container.content = self._build_empty_webhooks()
        
        self.update()
    
    def _build_webhook_card(self, webhook: dict) -> ft.Container:
        """Build a webhook card."""
        wh_id = webhook.get("id", "")
        url = webhook.get("url", "No URL")
        events = webhook.get("events", [])
        is_active = webhook.get("is_active", True)
        created_at = webhook.get("created_at", "")
        last_triggered = webhook.get("last_triggered_at", "Never")
        
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.WEBHOOK, color=config.PRIMARY_COLOR),
                            ft.Column(
                                [
                                    ft.Text(url, color="white", size=14, weight=ft.FontWeight.W_500),
                                    ft.Text(f"Created: {created_at[:10] if created_at else 'Unknown'}", color="grey", size=11),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            StatusBadge("active" if is_active else "inactive"),
                            ft.PopupMenuButton(
                                icon=ft.Icons.MORE_VERT,
                                items=[
                                    ft.PopupMenuItem(
                                        text="Test Webhook",
                                        icon=ft.Icons.PLAY_ARROW,
                                        on_click=lambda e, wid=wh_id: self._test_webhook(wid),
                                    ),
                                    ft.PopupMenuItem(
                                        text="Disable" if is_active else "Enable",
                                        icon=ft.Icons.PAUSE if is_active else ft.Icons.PLAY_ARROW,
                                        on_click=lambda e, wid=wh_id, active=is_active: self._toggle_webhook(wid, active),
                                    ),
                                    ft.PopupMenuItem(
                                        text="Delete",
                                        icon=ft.Icons.DELETE,
                                        on_click=lambda e, wid=wh_id: self._delete_webhook(wid),
                                    ),
                                ],
                            ),
                        ],
                        spacing=15,
                    ),
                    ft.Divider(height=10, color=config.BORDER_COLOR),
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("Events", size=11, color="grey"),
                                    ft.Row(
                                        [
                                            ft.Container(
                                                content=ft.Text(event, size=10, color="white"),
                                                bgcolor=config.PRIMARY_COLOR + "40",
                                                border_radius=4,
                                                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                            )
                                            for event in events[:3]
                                        ] + (
                                            [ft.Text(f"+{len(events) - 3} more", color="grey", size=10)]
                                            if len(events) > 3 else []
                                        ),
                                        spacing=5,
                                        wrap=True,
                                    ),
                                ],
                                spacing=5,
                                expand=True,
                            ),
                            ft.Column(
                                [
                                    ft.Text("Last Triggered", size=11, color="grey"),
                                    ft.Text(
                                        last_triggered[:16] if last_triggered and last_triggered != "Never" else "Never",
                                        color="white",
                                        size=12,
                                    ),
                                ],
                                spacing=5,
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                            ),
                        ],
                    ),
                ],
            ),
            bgcolor=config.SURFACE_COLOR,
            border_radius=10,
            padding=15,
        )
    
    def _build_stat_box(self, label: str, value: int, icon, color: str = None) -> ft.Container:
        """Build a small stat box."""
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, color=color or config.PRIMARY_COLOR, size=32),
                    ft.Column(
                        [
                            ft.Text(str(value), size=22, weight=ft.FontWeight.BOLD, color="white"),
                            ft.Text(label, size=11, color="grey"),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=15,
            ),
            bgcolor=config.SURFACE_COLOR,
            border_radius=10,
            padding=15,
            expand=True,
        )
    
    def _build_empty_webhooks(self):
        """Build empty state for webhooks."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.WEBHOOK, size=64, color="grey"),
                    ft.Text("No Webhooks Configured", size=18, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text(
                        "Create webhooks to receive real-time notifications about events",
                        color="grey",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=20),
                    ft.ElevatedButton(
                        "Create Your First Webhook",
                        icon=ft.Icons.ADD,
                        bgcolor=config.PRIMARY_COLOR,
                        color="white",
                        on_click=self._show_create_webhook_dialog,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
            expand=True,
            alignment=ft.alignment.center,
        )
    
    def _show_create_webhook_dialog(self, e):
        """Show dialog to create new webhook."""
        url_field = ft.TextField(
            label="Webhook URL",
            hint_text="https://your-domain.com/webhook",
            prefix_icon=ft.Icons.LINK,
        )
        
        events_checkboxes = [
            ft.Checkbox(label="tenant.created", value=True),
            ft.Checkbox(label="tenant.updated", value=False),
            ft.Checkbox(label="tenant.suspended", value=True),
            ft.Checkbox(label="subscription.changed", value=True),
            ft.Checkbox(label="payment.received", value=False),
            ft.Checkbox(label="user.created", value=False),
        ]
        
        def on_submit(e):
            url = url_field.value
            if not url or not url.startswith("http"):
                show_snackbar(self.app.page, "Please enter a valid URL", error=True)
                return
            
            selected_events = [cb.label for cb in events_checkboxes if cb.value]
            if not selected_events:
                show_snackbar(self.app.page, "Select at least one event", error=True)
                return
            
            result = api_client.create_webhook({
                "url": url,
                "events": selected_events,
                "is_active": True,
            })
            
            if result and not result.get("error"):
                show_snackbar(self.app.page, "Webhook created successfully")
                dialog.open = False
                self._load_webhooks()
            else:
                show_snackbar(self.app.page, result.get("error", "Failed to create webhook"), error=True)
            
            self.app.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Create Webhook"),
            content=ft.Container(
                content=ft.Column(
                    [
                        url_field,
                        ft.Container(height=15),
                        ft.Text("Events to Subscribe", weight=ft.FontWeight.W_500),
                        ft.Column(events_checkboxes, spacing=5),
                    ],
                    spacing=10,
                    tight=True,
                ),
                width=400,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: setattr(dialog, "open", False) or self.app.page.update()),
                ft.ElevatedButton(
                    "Create",
                    bgcolor=config.PRIMARY_COLOR,
                    color="white",
                    on_click=on_submit,
                ),
            ],
        )
        
        self.app.page.overlay.append(dialog)
        dialog.open = True
        self.app.page.update()
    
    def _test_webhook(self, webhook_id: str):
        """Send test payload to webhook."""
        result = api_client.test_webhook(webhook_id)
        if result and not result.get("error"):
            show_snackbar(self.app.page, "Test payload sent successfully")
        else:
            show_snackbar(self.app.page, result.get("error", "Failed to send test"), error=True)
    
    def _toggle_webhook(self, webhook_id: str, currently_active: bool):
        """Toggle webhook active state."""
        result = api_client.update_webhook(webhook_id, {"is_active": not currently_active})
        if result and not result.get("error"):
            show_snackbar(self.app.page, f"Webhook {'disabled' if currently_active else 'enabled'}")
            self._load_webhooks()
        else:
            show_snackbar(self.app.page, result.get("error", "Failed to update webhook"), error=True)
    
    def _delete_webhook(self, webhook_id: str):
        """Delete a webhook."""
        def on_confirm():
            result = api_client.delete_webhook(webhook_id)
            if result is None or (result and not result.get("error")):
                show_snackbar(self.app.page, "Webhook deleted")
                self._load_webhooks()
            else:
                show_snackbar(self.app.page, "Failed to delete webhook", error=True)
        
        dialog = ConfirmDialog(
            title="Delete Webhook",
            message="Are you sure you want to delete this webhook? This action cannot be undone.",
            on_confirm=on_confirm,
            confirm_text="Delete",
            is_destructive=True,
        )
        self.app.page.overlay.append(dialog)
        dialog.open = True
        self.app.page.update()
    
    def _load_api_info(self):
        """Load API documentation/info section."""
        # Build API reference section
        api_sections = [
            {
                "category": "Authentication",
                "endpoints": [
                    {"method": "POST", "path": "/auth/login", "desc": "Login and get JWT token"},
                    {"method": "POST", "path": "/auth/refresh", "desc": "Refresh access token"},
                    {"method": "POST", "path": "/auth/logout", "desc": "Invalidate current token"},
                ],
            },
            {
                "category": "Super Admin",
                "endpoints": [
                    {"method": "GET", "path": "/super-admin/stats", "desc": "Get system statistics"},
                    {"method": "GET", "path": "/super-admin/tenants", "desc": "List all tenants"},
                    {"method": "POST", "path": "/super-admin/tenants", "desc": "Create new tenant"},
                    {"method": "GET", "path": "/super-admin/subscription-plans", "desc": "List subscription plans"},
                    {"method": "GET", "path": "/super-admin/compliance", "desc": "Check PCI compliance"},
                ],
            },
            {
                "category": "Monitoring",
                "endpoints": [
                    {"method": "GET", "path": "/monitoring/health/detailed", "desc": "Detailed health check"},
                    {"method": "GET", "path": "/monitoring/celery/workers", "desc": "Celery worker status"},
                    {"method": "GET", "path": "/monitoring/database/stats", "desc": "Database statistics"},
                ],
            },
        ]
        
        sections = []
        for section in api_sections:
            endpoint_rows = []
            for ep in section["endpoints"]:
                method_color = {
                    "GET": config.SUCCESS_COLOR,
                    "POST": config.PRIMARY_COLOR,
                    "PUT": config.WARNING_COLOR,
                    "DELETE": config.ERROR_COLOR,
                }.get(ep["method"], "grey")
                
                endpoint_rows.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(
                                    content=ft.Text(ep["method"], size=11, weight=ft.FontWeight.BOLD, color="white"),
                                    bgcolor=method_color,
                                    border_radius=4,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                    width=60,
                                    alignment=ft.alignment.center,
                                ),
                                ft.Text(ep["path"], color="white", size=13, font_family="monospace", expand=True),
                                ft.Text(ep["desc"], color="grey", size=12),
                            ],
                            spacing=15,
                        ),
                        padding=ft.padding.symmetric(vertical=8, horizontal=10),
                        border=ft.border.only(bottom=ft.BorderSide(1, "#3d4043")),
                    )
                )
            
            sections.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(section["category"], size=16, weight=ft.FontWeight.BOLD, color="white"),
                            ft.Container(height=10),
                            ft.Column(endpoint_rows, spacing=0),
                        ],
                    ),
                    bgcolor=config.SURFACE_COLOR,
                    border_radius=10,
                    padding=15,
                )
            )
        
        self.api_container.content = ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.API, color=config.PRIMARY_COLOR, size=32),
                            ft.Column(
                                [
                                    ft.Text("API Reference", size=18, weight=ft.FontWeight.BOLD, color="white"),
                                    ft.Text("Core endpoints available for integration", color="grey"),
                                ],
                                spacing=2,
                            ),
                            ft.Container(expand=True),
                            ft.OutlinedButton(
                                "Open Full Docs",
                                icon=ft.Icons.OPEN_IN_NEW,
                                on_click=lambda e: self.app.page.launch_url(f"{config.API_BASE_URL}/docs"),
                            ),
                        ],
                        spacing=15,
                    ),
                    bgcolor=config.SURFACE_COLOR,
                    border_radius=12,
                    padding=20,
                ),
                ft.Container(height=20),
                ft.Column(sections, spacing=15),
            ],
            scroll=ft.ScrollMode.AUTO,
        )
        
        self.update()
