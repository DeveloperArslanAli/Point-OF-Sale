"""Stat card component for dashboard displays."""
import flet as ft

from config import config


class StatCard(ft.Container):
    """A card displaying a statistic with icon and optional trend."""
    
    def __init__(
        self,
        title: str,
        value: str,
        icon: str,
        subtitle: str | None = None,
        trend_value: float | None = None,
        trend_label: str | None = None,
        width: int = 220,
        height: int = 120,
        icon_color: str | None = None,
        on_click=None,
    ):
        super().__init__()
        self.title = title
        self._value = value
        self.icon = icon
        self.subtitle = subtitle
        self.trend_value = trend_value
        self.trend_label = trend_label
        self._icon_color = icon_color or config.PRIMARY_COLOR
        
        # Container styling
        self.width = width
        self.height = height
        self.bgcolor = config.SURFACE_COLOR
        self.border_radius = 12
        self.padding = 15
        self.on_click = on_click
        self.ink = bool(on_click)
        
        self._build()
    
    def _build(self):
        """Build card content."""
        # Trend indicator
        trend_control = None
        if self.trend_value is not None:
            is_positive = self.trend_value >= 0
            trend_color = config.SUCCESS_COLOR if is_positive else config.ERROR_COLOR
            trend_icon = ft.Icons.TRENDING_UP if is_positive else ft.Icons.TRENDING_DOWN
            
            trend_control = ft.Row(
                [
                    ft.Icon(trend_icon, color=trend_color, size=16),
                    ft.Text(
                        f"{abs(self.trend_value):.1f}%",
                        size=12,
                        color=trend_color,
                    ),
                    ft.Text(
                        self.trend_label or "",
                        size=10,
                        color="grey",
                    ),
                ],
                spacing=4,
            )
        
        # Value text
        self.value_text = ft.Text(
            self._value,
            size=24,
            weight=ft.FontWeight.BOLD,
            color="white",
        )
        
        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(self.icon, color=self._icon_color, size=28),
                            bgcolor=f"{self._icon_color}20",
                            border_radius=8,
                            padding=8,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    self.title,
                                    size=12,
                                    color="grey",
                                ),
                            ],
                            spacing=0,
                            expand=True,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                self.value_text,
                trend_control or (
                    ft.Text(self.subtitle, size=11, color="grey")
                    if self.subtitle else ft.Container()
                ),
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
    
    def update_value(self, new_value: str):
        """Update the displayed value."""
        self._value = new_value
        if hasattr(self, "value_text"):
            self.value_text.value = new_value
            self.value_text.update()
    
    @property
    def value(self) -> str:
        return self._value
    
    @value.setter
    def value(self, new_value: str):
        self.update_value(new_value)


class StatCardRow(ft.Row):
    """A row of stat cards with responsive layout."""
    
    def __init__(self, cards: list[StatCard]):
        super().__init__(
            controls=cards,
            wrap=True,
            spacing=15,
            run_spacing=15,
        )
