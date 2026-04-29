"""Navigation sidebar component."""
from dataclasses import dataclass
from typing import Callable

import flet as ft

from config import config


@dataclass
class NavItem:
    """Navigation item definition."""
    
    id: str
    title: str
    icon: str
    route: str
    children: list["NavItem"] | None = None


class Sidebar(ft.Container):
    """Collapsible navigation sidebar."""
    
    DEFAULT_NAV_ITEMS = [
        NavItem("dashboard", "Dashboard", ft.Icons.DASHBOARD, "dashboard"),
        NavItem("tenants", "Tenants", ft.Icons.BUSINESS, "tenants"),
        NavItem("plans", "Subscription Plans", ft.Icons.CARD_MEMBERSHIP, "plans"),
        NavItem("billing", "Billing & Revenue", ft.Icons.ATTACH_MONEY, "billing"),
        NavItem("monitoring", "System Monitoring", ft.Icons.MONITOR_HEART, "monitoring"),
        NavItem("compliance", "Compliance", ft.Icons.SECURITY, "compliance"),
        NavItem("analytics", "Analytics", ft.Icons.ANALYTICS, "analytics"),
        NavItem("reports", "Reports", ft.Icons.ASSESSMENT, "reports"),
        NavItem("integrations", "Integrations", ft.Icons.WEBHOOK, "integrations"),
        NavItem("settings", "Settings", ft.Icons.SETTINGS, "settings"),
    ]
    
    def __init__(
        self,
        on_navigate: Callable[[str], None],
        selected_route: str = "dashboard",
        nav_items: list[NavItem] | None = None,
        collapsed: bool = False,
    ):
        super().__init__()
        self.on_navigate = on_navigate
        self.selected_route = selected_route
        self.nav_items = nav_items or self.DEFAULT_NAV_ITEMS
        self._collapsed = collapsed
        
        # Styling
        self.bgcolor = config.SURFACE_COLOR
        self.border_radius = ft.border_radius.only(top_right=10, bottom_right=10)
        self.padding = ft.padding.symmetric(vertical=20, horizontal=10)
        self.width = 60 if collapsed else 240
        self.animate = ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT)
        
        self._build()
    
    def _build(self):
        """Build sidebar content."""
        # Header with logo
        header = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS, color=config.PRIMARY_COLOR, size=32),
                    ft.Text(
                        "SuperAdmin",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color="white",
                        visible=not self._collapsed,
                    ),
                ],
                spacing=10,
            ),
            margin=ft.margin.only(bottom=20),
        )
        
        # Navigation items
        nav_buttons = [self._build_nav_button(item) for item in self.nav_items]
        
        # Collapse toggle
        collapse_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT if not self._collapsed else ft.Icons.CHEVRON_RIGHT,
            icon_color="grey",
            tooltip="Collapse" if not self._collapsed else "Expand",
            on_click=self._toggle_collapse,
        )
        
        self.content = ft.Column(
            [
                header,
                ft.Column(nav_buttons, spacing=5, expand=True, scroll=ft.ScrollMode.AUTO),
                ft.Divider(color="#3d4043"),
                collapse_btn,
            ],
            expand=True,
        )
    
    def _build_nav_button(self, item: NavItem) -> ft.Container:
        """Build a navigation button."""
        is_selected = item.route == self.selected_route
        
        btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        item.icon,
                        color=config.PRIMARY_COLOR if is_selected else "grey",
                        size=24,
                    ),
                    ft.Text(
                        item.title,
                        color="white" if is_selected else "grey",
                        size=14,
                        weight=ft.FontWeight.W_500 if is_selected else ft.FontWeight.NORMAL,
                        visible=not self._collapsed,
                    ),
                ],
                spacing=15,
            ),
            padding=ft.padding.symmetric(vertical=12, horizontal=10),
            border_radius=8,
            bgcolor=f"{config.PRIMARY_COLOR}20" if is_selected else None,
            on_click=lambda e, route=item.route: self._on_nav_click(route),
            on_hover=self._on_hover,
            ink=True,
        )
        
        return btn
    
    def _on_nav_click(self, route: str):
        """Handle navigation click."""
        self.selected_route = route
        self._build()
        self.update()
        self.on_navigate(route)
    
    def _on_hover(self, e: ft.ControlEvent):
        """Handle hover state."""
        if e.data == "true":
            e.control.bgcolor = f"{config.PRIMARY_COLOR}10"
        else:
            is_selected = False
            for item in self.nav_items:
                if item.route == self.selected_route:
                    # Check if this is the selected item
                    row = e.control.content
                    if hasattr(row, "controls") and len(row.controls) > 1:
                        text = row.controls[1]
                        if hasattr(text, "value") and text.value == item.title:
                            is_selected = True
                            break
            
            e.control.bgcolor = f"{config.PRIMARY_COLOR}20" if is_selected else None
        e.control.update()
    
    def _toggle_collapse(self, e):
        """Toggle sidebar collapse state."""
        self._collapsed = not self._collapsed
        self.width = 60 if self._collapsed else 240
        self._build()
        self.update()
    
    def set_selected(self, route: str):
        """Set the selected route."""
        self.selected_route = route
        self._build()
        self.update()
