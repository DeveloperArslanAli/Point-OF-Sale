"""Dialog components for modals and confirmations."""
from typing import Callable

import flet as ft

from config import config


def show_snackbar(page: ft.Page, message: str, error: bool = False, duration: int = 3000):
    """Show a snackbar notification.
    
    Args:
        page: The Flet page
        message: Message to display
        error: True for error styling (red), False for success (green)
        duration: Display duration in milliseconds
    """
    page.snack_bar = ft.SnackBar(
        content=ft.Text(message, color="white"),
        bgcolor=config.ERROR_COLOR if error else config.SUCCESS_COLOR,
        duration=duration,
    )
    page.snack_bar.open = True
    page.update()


class ConfirmDialog(ft.AlertDialog):
    """Confirmation dialog for dangerous actions."""
    
    def __init__(
        self,
        title: str,
        message: str,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
        on_confirm: Callable[[], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        danger: bool = False,
    ):
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        
        super().__init__(
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Text(message),
            actions=[
                ft.TextButton(
                    cancel_text,
                    on_click=self._handle_cancel,
                ),
                ft.ElevatedButton(
                    confirm_text,
                    bgcolor=config.ERROR_COLOR if danger else config.PRIMARY_COLOR,
                    color="white",
                    on_click=self._handle_confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    
    def _handle_confirm(self, e):
        """Handle confirm click."""
        self.open = False
        if self.page:
            self.page.update()
        if self._on_confirm:
            self._on_confirm()
    
    def _handle_cancel(self, e):
        """Handle cancel click."""
        self.open = False
        if self.page:
            self.page.update()
        if self._on_cancel:
            self._on_cancel()


class FormDialog(ft.AlertDialog):
    """Dialog with form fields."""
    
    def __init__(
        self,
        title: str,
        fields: list[ft.Control],
        submit_text: str = "Submit",
        cancel_text: str = "Cancel",
        on_submit: Callable[[], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        width: int = 400,
        height: int | None = None,
    ):
        self._on_submit = on_submit
        self._on_cancel = on_cancel
        self.fields = fields
        
        content = ft.Container(
            content=ft.Column(
                fields,
                spacing=15,
                scroll=ft.ScrollMode.AUTO if height else None,
            ),
            width=width,
            height=height,
        )
        
        super().__init__(
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=content,
            actions=[
                ft.TextButton(
                    cancel_text,
                    on_click=self._handle_cancel,
                ),
                ft.ElevatedButton(
                    submit_text,
                    bgcolor=config.PRIMARY_COLOR,
                    color="white",
                    on_click=self._handle_submit,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    
    def _handle_submit(self, e):
        """Handle submit click."""
        self.open = False
        if self.page:
            self.page.update()
        if self._on_submit:
            self._on_submit()
    
    def _handle_cancel(self, e):
        """Handle cancel click."""
        self.open = False
        if self.page:
            self.page.update()
        if self._on_cancel:
            self._on_cancel()
    
    def get_field_values(self) -> dict:
        """Get values from all text fields."""
        values = {}
        for field in self.fields:
            if isinstance(field, ft.TextField) and field.data:
                values[field.data] = field.value
            elif isinstance(field, ft.Dropdown) and field.data:
                values[field.data] = field.value
        return values


class AlertDialog(ft.AlertDialog):
    """Simple alert dialog for information display."""
    
    def __init__(
        self,
        title: str,
        content: ft.Control | str,
        close_text: str = "Close",
        on_close: Callable[[], None] | None = None,
    ):
        self._on_close = on_close
        
        if isinstance(content, str):
            content = ft.Text(content)
        
        super().__init__(
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=content,
            actions=[
                ft.TextButton(
                    close_text,
                    on_click=self._handle_close,
                ),
            ],
        )
    
    def _handle_close(self, e):
        """Handle close click."""
        self.open = False
        if self.page:
            self.page.update()
        if self._on_close:
            self._on_close()
