import flet as ft
from services.api import api_service

icons = ft.icons

class EmployeesView(ft.Container):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 20
        self.employees = []
        
        # UI Components
        self.search_field = ft.TextField(
            hint_text="Search employees...",
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
                ft.DataColumn(ft.Text("Name")),
                ft.DataColumn(ft.Text("Position")),
                ft.DataColumn(ft.Text("Email")),
                ft.DataColumn(ft.Text("Status")),
                ft.DataColumn(ft.Text("Actions")),
            ],
            rows=[],
            heading_row_color="#2d3033",
            data_row_color={"hovered": "#2d3033"},
        )

        # Check permissions
        can_manage = self.app.user_role == "ADMIN"

        header_controls = [
            ft.Text("Employee Management", size=24, weight=ft.FontWeight.BOLD, color="white"),
            ft.Container(expand=True),
        ]

        if can_manage:
            header_controls.append(
                ft.ElevatedButton(
                    "Add Employee",
                    icon=icons.ADD,
                    bgcolor="#bb86fc",
                    color="black",
                    on_click=self._open_add_dialog
                )
            )

        self.content = ft.Column(
            [
                ft.Row(
                    header_controls,
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
        self.employees = api_service.get_employees(search=search)
        self._render_table()

    def _render_table(self):
        self.data_table.rows = []
        for emp in self.employees:
            status_color = "#03dac6" if emp["is_active"] else "#cf6679"
            status_text = "Active" if emp["is_active"] else "Inactive"
            
            actions = [
                ft.IconButton(
                    icon=icons.EDIT, 
                    icon_color="#03dac6", 
                    tooltip="Edit Details",
                    on_click=lambda e, emp=emp: self._open_edit_dialog(emp)
                )
            ]

            if self.app.user_role == "ADMIN":
                actions.append(
                    ft.IconButton(
                        icon=icons.ATTACH_MONEY, 
                        icon_color="#bb86fc", 
                        tooltip="Financials",
                        on_click=lambda e, emp=emp: self._open_financial_dialog(emp)
                    )
                )

            self.data_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"{emp['first_name']} {emp['last_name']}", color="white")),
                        ft.DataCell(ft.Text(emp['position'], color="white")),
                        ft.DataCell(ft.Text(emp['email'], color="grey")),
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

    def _open_add_dialog(self, e):
        first_name = ft.TextField(label="First Name", bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
        last_name = ft.TextField(label="Last Name", bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
        email = ft.TextField(label="Email", bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
        phone = ft.TextField(label="Phone", bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
        position = ft.TextField(label="Position", bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
        
        hire_date = ft.TextField(
            label="Hire Date (YYYY-MM-DD)", 
            bgcolor="#2d3033", 
            color="white", 
            border_color="#bb86fc", 
            width=400,
            read_only=True
        )
        
        def handle_date_change(e):
            hire_date.value = e.control.value.strftime('%Y-%m-%d')
            hire_date.update()

        date_picker = ft.DatePicker(
            on_change=handle_date_change,
        )
        self.page.overlay.append(date_picker)
        
        hire_date.suffix = ft.IconButton(
            icon=ft.icons.CALENDAR_MONTH,
            on_click=lambda _: date_picker.pick_date()
        )

        base_salary = ft.TextField(label="Base Salary", bgcolor="#2d3033", color="white", border_color="#bb86fc", keyboard_type=ft.KeyboardType.NUMBER, width=400)

        # User Account Fields
        password_field = ft.TextField(label="Password", password=True, can_reveal_password=True, bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400, visible=False)
        
        def toggle_user_fields(e):
            password_field.visible = e.control.value
            dlg.content.update()

        create_user_checkbox = ft.Checkbox(label="Create User Account (Role: CASHIER)", on_change=toggle_user_fields, fill_color="#bb86fc")

        def save(e):
            try:
                required_fields = [first_name.value, last_name.value, email.value, position.value]
                missing_basic = any(not v or not str(v).strip() for v in required_fields)
                missing_hire = not hire_date.value or not str(hire_date.value).strip()
                if missing_basic or missing_hire:
                    self.page.show_snack_bar(ft.SnackBar(content=ft.Text("First, last, email, position, and hire date are required")))
                    return

                try:
                    salary_value = float(base_salary.value) if base_salary.value else 0
                except ValueError:
                    self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Base salary must be a number")))
                    return

                data = {
                    "first_name": first_name.value,
                    "last_name": last_name.value,
                    "email": email.value,
                    "phone": phone.value,
                    "position": position.value,
                    "hire_date": hire_date.value,
                    "base_salary": salary_value,
                    "create_user_account": create_user_checkbox.value
                }
                
                if create_user_checkbox.value:
                    if not password_field.value:
                        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Password is required for user account")))
                        return
                    data["password"] = password_field.value
                    data["role"] = "CASHIER"

                if api_service.create_employee(data):
                    self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Employee added!")))
                    dlg.open = False
                    self._load_data()
                    self.page.update()
                else:
                    status = api_service.last_error_status
                    error_msg = api_service.last_error_message or "Error adding employee"
                    if status == 409:
                        error_msg = "Employee with this email already exists (409)"
                    self.page.show_snack_bar(ft.SnackBar(content=ft.Text(error_msg)))
            except Exception as ex:
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text(f"Error: {str(ex)}")))

        def close_dialog(_):
            dlg.open = False
            self.page.dialog = None
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Add Employee"),
            content=ft.Column(
                [
                    first_name, last_name, email, phone, position, hire_date, base_salary,
                    ft.Divider(),
                    create_user_checkbox,
                    password_field
                ], 
                tight=True, 
                scroll=ft.ScrollMode.AUTO,
                height=500,
                width=450
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.ElevatedButton("Save", on_click=save, bgcolor="#bb86fc", color="black"),
            ],
            bgcolor="#1a1c1e",
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _open_edit_dialog(self, emp):
        first_name = ft.TextField(label="First Name", value=emp.get("first_name", ""), bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
        last_name = ft.TextField(label="Last Name", value=emp.get("last_name", ""), bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
        email = ft.TextField(label="Email", value=emp.get("email", ""), bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
        phone = ft.TextField(label="Phone", value=emp.get("phone") or "", bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
        position = ft.TextField(label="Position", value=emp.get("position", ""), bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
        active_switch = ft.Switch(label="Active", value=emp.get("is_active", True), active_color="#03dac6")

        def save(e):
            required_fields = [first_name.value, last_name.value, email.value, position.value]
            if any(not v or not str(v).strip() for v in required_fields):
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("First, last, email, and position are required")))
                return

            payload = {
                "first_name": first_name.value,
                "last_name": last_name.value,
                "email": email.value,
                "phone": phone.value,
                "position": position.value,
                "is_active": active_switch.value,
            }

            if api_service.update_employee(emp["id"], payload):
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Employee updated")))
                dlg.open = False
                self._load_data()
                self.page.update()
            else:
                error_msg = api_service.last_error_message or "Error updating employee"
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text(error_msg)))

        def close_dialog(_):
            dlg.open = False
            self.page.dialog = None
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Edit Employee"),
            content=ft.Column(
                [first_name, last_name, email, phone, position, active_switch],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                height=450,
                width=450,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.ElevatedButton("Save", on_click=save, bgcolor="#bb86fc", color="black"),
            ],
            bgcolor="#1a1c1e",
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _open_financial_dialog(self, emp):
        history = api_service.get_financial_history(emp['id'])
        if not history:
            return

        # Salary History Table
        salary_rows = []
        for h in history.get("salary_history", []):
            salary_rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(h["change_date"], color="white")),
                    ft.DataCell(ft.Text(f"${h['previous_salary']}", color="grey")),
                    ft.DataCell(ft.Text(f"${h['new_salary']}", color="#03dac6", weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(h["reason"], color="white")),
                ])
            )
            
        salary_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("Previous")),
                ft.DataColumn(ft.Text("New")),
                ft.DataColumn(ft.Text("Reason")),
            ],
            rows=salary_rows,
            heading_row_color="#2d3033",
        )

        # Bonus History Table
        bonus_rows = []
        for b in history.get("bonuses", []):
            bonus_rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(b["date_awarded"], color="white")),
                    ft.DataCell(ft.Text(f"${b['amount']}", color="#bb86fc", weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(b["reason"], color="white")),
                ])
            )

        bonus_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("Amount")),
                ft.DataColumn(ft.Text("Reason")),
            ],
            rows=bonus_rows,
            heading_row_color="#2d3033",
        )

        def open_increment_dialog(e):
            new_salary = ft.TextField(label="New Salary", value=str(emp['base_salary']), bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
            reason = ft.TextField(label="Reason", bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
            
            date_field = ft.TextField(
                label="Date (YYYY-MM-DD)", 
                bgcolor="#2d3033", 
                color="white", 
                border_color="#bb86fc", 
                width=400,
                read_only=True
            )
            
            def handle_inc_date_change(e):
                date_field.value = e.control.value.strftime('%Y-%m-%d')
                date_field.update()

            inc_date_picker = ft.DatePicker(
                on_change=handle_inc_date_change,
            )
            self.page.overlay.append(inc_date_picker)
            
            date_field.suffix = ft.IconButton(
                icon=ft.icons.CALENDAR_MONTH,
                on_click=lambda _: inc_date_picker.pick_date()
            )

            def save_inc(e):
                try:
                    data = {
                        "new_salary": float(new_salary.value),
                        "reason": reason.value,
                        "change_date": date_field.value if date_field.value else None
                    }
                    if api_service.grant_increment(emp['id'], data):
                        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Increment granted!")))
                        inc_dlg.open = False
                        dlg.open = False # Close parent too to refresh
                        self._load_data()
                        self.page.update()
                    else:
                        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Error granting increment")))
                except Exception as ex:
                    self.page.show_snack_bar(ft.SnackBar(content=ft.Text(f"Error: {str(ex)}")))

            def close_inc(_):
                inc_dlg.open = False
                self.page.update()

            inc_dlg = ft.AlertDialog(
                title=ft.Text("Grant Increment"),
                content=ft.Column([new_salary, reason, date_field], tight=True, scroll=ft.ScrollMode.AUTO, width=450),
                actions=[
                    ft.TextButton("Cancel", on_click=close_inc),
                    ft.ElevatedButton("Save", on_click=save_inc, bgcolor="#bb86fc", color="black"),
                ],
                bgcolor="#1a1c1e",
            )
            self.page.dialog = inc_dlg
            inc_dlg.open = True
            self.page.update()

        def open_bonus_dialog(e):
            amount = ft.TextField(label="Amount", bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
            reason = ft.TextField(label="Reason", bgcolor="#2d3033", color="white", border_color="#bb86fc", width=400)
            
            date_field = ft.TextField(
                label="Date (YYYY-MM-DD)", 
                bgcolor="#2d3033", 
                color="white", 
                border_color="#bb86fc", 
                width=400,
                read_only=True
            )
            
            def handle_bonus_date_change(e):
                date_field.value = e.control.value.strftime('%Y-%m-%d')
                date_field.update()

            bonus_date_picker = ft.DatePicker(
                on_change=handle_bonus_date_change,
            )
            self.page.overlay.append(bonus_date_picker)
            
            date_field.suffix = ft.IconButton(
                icon=ft.icons.CALENDAR_MONTH,
                on_click=lambda _: bonus_date_picker.pick_date()
            )

            def save_bonus(e):
                try:
                    data = {
                        "amount": float(amount.value),
                        "reason": reason.value,
                        "date_awarded": date_field.value if date_field.value else None
                    }
                    if api_service.give_bonus(emp['id'], data):
                        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Bonus awarded!")))
                        bonus_dlg.open = False
                        dlg.open = False
                        self._load_data()
                        self.page.update()
                    else:
                        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Error awarding bonus")))
                except Exception as ex:
                    self.page.show_snack_bar(ft.SnackBar(content=ft.Text(f"Error: {str(ex)}")))

            def close_bonus(_):
                bonus_dlg.open = False
                self.page.update()

            bonus_dlg = ft.AlertDialog(
                title=ft.Text("Award Bonus"),
                content=ft.Column([amount, reason, date_field], tight=True, scroll=ft.ScrollMode.AUTO, width=450),
                actions=[
                    ft.TextButton("Cancel", on_click=close_bonus),
                    ft.ElevatedButton("Save", on_click=save_bonus, bgcolor="#bb86fc", color="black"),
                ],
                bgcolor="#1a1c1e",
            )
            self.page.dialog = bonus_dlg
            bonus_dlg.open = True
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(f"Financials: {emp['first_name']} {emp['last_name']}"),
            content=ft.Column([
                ft.Text(f"Current Base Salary: ${emp['base_salary']}", size=20, weight=ft.FontWeight.BOLD, color="#03dac6"),
                ft.Row([
                    ft.ElevatedButton("Grant Increment", on_click=open_increment_dialog, bgcolor="#03dac6", color="black"),
                    ft.ElevatedButton("Give Bonus", on_click=open_bonus_dialog, bgcolor="#bb86fc", color="black"),
                ]),
                ft.Divider(),
                ft.Tabs(
                    selected_index=0,
                    tabs=[
                        ft.Tab(text="Salary History", content=salary_table),
                        ft.Tab(text="Bonuses", content=bonus_table),
                    ],
                    expand=True,
                )
            ], width=600, height=500),
            actions=[
                ft.TextButton("Close", on_click=lambda e: (setattr(dlg, 'open', False), self.page.update())),
            ],
            bgcolor="#1a1c1e",
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()
