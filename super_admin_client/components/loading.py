"""Loading indicator components."""
import flet as ft

from config import config


class LoadingIndicator(ft.Container):
    """Simple loading spinner."""
    
    def __init__(
        self,
        size: int = 30,
        message: str | None = None,
        color: str | None = None,
    ):
        super().__init__()
        self.alignment = ft.alignment.center
        
        controls = [
            ft.ProgressRing(
                width=size,
                height=size,
                color=color or config.PRIMARY_COLOR,
                stroke_width=3,
            ),
        ]
        
        if message:
            controls.append(
                ft.Text(message, color="grey", size=12)
            )
        
        self.content = ft.Column(
            controls,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        )


class LoadingOverlay(ft.Container):
    """Full-screen loading overlay."""
    
    def __init__(
        self,
        message: str = "Loading...",
        visible: bool = False,
    ):
        super().__init__()
        self._visible = visible
        self.expand = True
        self.bgcolor = "#000000aa"
        self.alignment = ft.alignment.center
        self.visible = visible
        
        self.content = ft.Column(
            [
                ft.ProgressRing(
                    width=50,
                    height=50,
                    color=config.PRIMARY_COLOR,
                    stroke_width=4,
                ),
                ft.Text(message, color="white", size=16),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        )
    
    def show(self, message: str | None = None):
        """Show the overlay."""
        if message and isinstance(self.content, ft.Column):
            for control in self.content.controls:
                if isinstance(control, ft.Text):
                    control.value = message
        self.visible = True
        self.update()
    
    def hide(self):
        """Hide the overlay."""
        self.visible = False
        self.update()
