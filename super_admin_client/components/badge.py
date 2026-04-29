"""Status badge component."""
import flet as ft

from config import config


class StatusBadge(ft.Container):
    """Status indicator badge."""
    
    STATUS_COLORS = {
        "active": config.SUCCESS_COLOR,
        "suspended": config.ERROR_COLOR,
        "pending": config.WARNING_COLOR,
        "inactive": "#757575",
        "healthy": config.SUCCESS_COLOR,
        "unhealthy": config.ERROR_COLOR,
        "degraded": config.WARNING_COLOR,
        "compliant": config.SUCCESS_COLOR,
        "non-compliant": config.ERROR_COLOR,
        "trial": "#2196f3",
        "expired": config.ERROR_COLOR,
    }
    
    def __init__(
        self,
        status: str,
        label: str | None = None,
        size: str = "medium",
    ):
        super().__init__()
        
        # Determine color
        status_lower = status.lower().replace("_", "-").replace(" ", "-")
        self.bgcolor = self.STATUS_COLORS.get(status_lower, "#757575")
        
        # Size configuration
        sizes = {
            "small": {"padding_h": 6, "padding_v": 2, "font_size": 10},
            "medium": {"padding_h": 10, "padding_v": 4, "font_size": 12},
            "large": {"padding_h": 14, "padding_v": 6, "font_size": 14},
        }
        size_config = sizes.get(size, sizes["medium"])
        
        self.padding = ft.padding.symmetric(
            horizontal=size_config["padding_h"],
            vertical=size_config["padding_v"],
        )
        self.border_radius = 12
        
        self.content = ft.Text(
            label or status.replace("_", " ").replace("-", " ").title(),
            size=size_config["font_size"],
            color="white",
            weight=ft.FontWeight.W_500,
        )
    
    def set_status(self, status: str, label: str | None = None):
        """Update the status."""
        status_lower = status.lower().replace("_", "-").replace(" ", "-")
        self.bgcolor = self.STATUS_COLORS.get(status_lower, "#757575")
        
        if isinstance(self.content, ft.Text):
            self.content.value = label or status.replace("_", " ").replace("-", " ").title()
        
        self.update()


class HealthIndicator(ft.Row):
    """Health status indicator with icon and text."""
    
    def __init__(
        self,
        label: str,
        status: str,
        details: str | None = None,
    ):
        status_lower = status.lower()
        
        if status_lower == "healthy":
            icon = ft.Icons.CHECK_CIRCLE
            color = config.SUCCESS_COLOR
        elif status_lower in ("degraded", "warning"):
            icon = ft.Icons.WARNING
            color = config.WARNING_COLOR
        else:
            icon = ft.Icons.ERROR
            color = config.ERROR_COLOR
        
        controls = [
            ft.Icon(icon, color=color, size=20),
            ft.Text(label, color="white", weight=ft.FontWeight.W_500),
            StatusBadge(status, size="small"),
        ]
        
        if details:
            controls.append(ft.Text(details, color="grey", size=11))
        
        super().__init__(controls=controls, spacing=10)
