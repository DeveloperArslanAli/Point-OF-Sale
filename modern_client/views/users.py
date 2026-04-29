import flet as ft
from services.api import api_service

icons = ft.icons

class UsersView(ft.Container):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 20
        self.users = []
        
        # UI Components
        self.search_field = ft.TextField(
            hint_text="Search users (email)...",
            prefix_icon=icons.SEARCH,
            bgcolor="#2d3033",
            border_radius=10,
            border_width=0,
            color="white",
            expand=True,
            on_change=self._on_search
        )

        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Email")),
                ft.DataColumn(ft.Text("Role")),
                ft.DataColumn(ft.Text("Status")),
                ft.DataColumn(ft.Text("Actions")),
            ],
            rows=[],
            heading_row_color="#2d3033",
            data_row_color={"hovered": "#2d3033"},
        )

        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Cashier Management", size=24, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            "Add Cashier",
                            icon=icons.ADD,
                            bgcolor="#bb86fc",
                            color="black",
                            on_click=self._open_add_cashier_dialog
                        ),
                        ft.IconButton(icons.REFRESH, icon_color="white", on_click=lambda e: self._load_data())
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                ft.Container(height=20),
                ft.Row([self.search_field]),
                ft.Container(height=20),
                ft.Container(
                    content=self.data_table,
                    bgcolor="#1a1c1e",
                    border_radius=10,
                    padding=10,
                )
            ],
            expand=True,
            scroll=ft.ScrollMode.HIDDEN
        )
        
        self._load_data()

    def _load_data(self, search=None):
        # Filter to show only Cashiers
        self.users = api_service.get_users(search=search, role="CASHIER")
        self._render_table()

    def _open_add_cashier_dialog(self, e):
        email = ft.TextField(label="Email", bgcolor="#2d3033", color="white", border_color="#bb86fc", width=320)
        password = ft.TextField(label="Password", password=True, can_reveal_password=True, bgcolor="#2d3033", color="white", border_color="#bb86fc", width=320)
        confirm_password = ft.TextField(label="Confirm Password", password=True, can_reveal_password=True, bgcolor="#2d3033", color="white", border_color="#bb86fc", width=320)

        create_button = ft.ElevatedButton("Create", bgcolor="#bb86fc", color="black")

        def set_loading(is_loading: bool) -> None:
            create_button.disabled = is_loading
            create_button.text = "Creating..." if is_loading else "Create"
            create_button.update()

        def save(e):
            if create_button.disabled:
                return

            if not all([email.value, password.value, confirm_password.value]):
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("All fields are required")))
                return
            if password.value != confirm_password.value:
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Passwords do not match")))
                return
            if len(password.value) < 8:
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Password must be at least 8 characters")))
                return

            email_value = email.value.strip()
            if not email_value:
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Email is required")))
                return
            set_loading(True)
            data = {
                "email": email_value,
                "password": password.value,
                "role": "CASHIER"
            }

            try:
                if api_service.create_user(data):
                    self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Cashier created successfully!")))
                    dlg.open = False
                    self._load_data()
                    self.page.update()
                else:
                    status = api_service.last_error_status
                    error_text = api_service.last_error_message or "Error creating cashier"
                    if status == 409:
                        error_text = "User with this email already exists (409)"
                    elif status == 400:
                        error_text = "Check email and password requirements (400)"
                    self.page.show_snack_bar(ft.SnackBar(content=ft.Text(error_text)))
            finally:
                set_loading(False)

        dlg = ft.AlertDialog(
            title=ft.Text("Add New Cashier"),
            content=ft.Column(
                [email, password, confirm_password],
                tight=True,
                height=260,
                width=360
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: setattr(dlg, 'open', False)),
                create_button,
            ],
            bgcolor="#1a1c1e",
        )
        create_button.on_click = save
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _render_table(self):
        self.data_table.rows = []
        for user in self.users:
            status_color = "#03dac6" if user["active"] else "#cf6679"
            status_text = "Active" if user["active"] else "Inactive"
            
            actions = [
                ft.IconButton(
                    icon=icons.LOCK_RESET, 
                    icon_color="#ffb74d", 
                    tooltip="Reset Password",
                    on_click=lambda e, u=user: self._open_password_dialog(u)
                )
            ]
            
            if user["active"]:
                actions.append(
                    ft.IconButton(
                        icon=icons.BLOCK, 
                        icon_color="#cf6679", 
                        tooltip="Deactivate",
                        on_click=lambda e, u=user: self._toggle_status(u)
                    )
                )
            else:
                actions.append(
                    ft.IconButton(
                        icon=icons.CHECK_CIRCLE, 
                        icon_color="#03dac6", 
                        tooltip="Activate",
                        on_click=lambda e, u=user: self._toggle_status(u)
                    )
                )

            self.data_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(user['email'], color="white")),
                        ft.DataCell(ft.Text(user['role'], color="white")),
                        ft.DataCell(ft.Container(
                            content=ft.Text(status_text, color="black", size=12),
                            bgcolor=status_color,
                            padding=5,
                            border_radius=5
                        )),
                        ft.DataCell(ft.Row(actions)),
                    ]
                )
            )
        if self.page:
            self.page.update()

    def _on_search(self, e):
        self._load_data(search=e.control.value)

    def _open_password_dialog(self, user):
        new_password = ft.TextField(
            label="New Password", 
            password=True, 
            can_reveal_password=True, 
            bgcolor="#2d3033", 
            color="white", 
            border_color="#bb86fc", 
            width=300
        )

        def save(e):
            if not new_password.value or len(new_password.value) < 8:
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Password must be at least 8 characters")))
                return

            if api_service.reset_user_password(user['id'], new_password.value, user['version']):
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Password reset successfully!")))
                dlg.open = False
                self._load_data()
                self.page.update()
            else:
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Error resetting password")))

        def close_dialog(_):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(f"Reset Password for {user['email']}"),
            content=new_password,
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.ElevatedButton("Reset", on_click=save, bgcolor="#cf6679", color="white"),
            ],
            bgcolor="#1a1c1e",
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _toggle_status(self, user):
        success = False
        if user['active']:
            success = api_service.deactivate_user(user['id'], user['version'])
            msg = "User deactivated"
        else:
            success = api_service.activate_user(user['id'], user['version'])
            msg = "User activated"
            
        if success:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
            self._load_data()
        else:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Error changing status")))
