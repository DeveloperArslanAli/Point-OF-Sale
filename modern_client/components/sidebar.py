import flet as ft
icons = ft.icons

class Sidebar(ft.Container):
    def __init__(self, app, page):
        super().__init__()
        self.app = app
        self.page = page
        self.width = 250
        self.bgcolor = "#2d3033"
        self.padding = 20
        self.content = self._build_content()

    def _build_content(self):
        role = self.app.user_role
        
        items = [
            ft.Text("Retail POS", size=24, weight=ft.FontWeight.BOLD, color="white"),
            ft.Divider(color="transparent", height=30),
        ]

        # Dashboard - Maybe restricted for Cashiers? Let's keep it for now or hide it.
        # Plan says: Cashier redirected to POS.
        if role in ["ADMIN", "MANAGER"]:
            items.append(self._build_nav_item(icons.DASHBOARD, "Dashboard", "dashboard"))
        
        items.append(self._build_nav_item(icons.POINT_OF_SALE, "POS Terminal", "pos"))
        items.append(self._build_nav_item(icons.RECEIPT_LONG, "Orders", "orders"))
        
        if role in ["ADMIN", "MANAGER", "INVENTORY"]:
            items.append(self._build_nav_item(icons.INVENTORY, "Inventory", "inventory"))
            items.append(self._build_nav_item(icons.ANALYTICS, "Intelligence", "intelligence"))
            
        items.append(self._build_nav_item(icons.PEOPLE, "Customers", "customers"))
        
        if role in ["ADMIN", "MANAGER"]:
            items.append(self._build_nav_item(icons.BADGE, "Employees", "employees"))

        if role == "ADMIN":
            items.append(self._build_nav_item(icons.POINT_OF_SALE, "Cashiers", "users"))
            items.append(self._build_nav_item(icons.CAMPAIGN, "Promotions", "promotions"))
            items.append(self._build_nav_item(icons.SETTINGS, "Settings", "settings"))
            
        items.append(self._build_nav_item(icons.ASSIGNMENT_RETURN, "Returns", "returns"))
        
        items.append(ft.Divider(color="grey"))
        items.append(self._build_nav_item(icons.LOGOUT, "Logout", "logout", color="#cf6679"))

        return ft.Column(items, spacing=10, scroll=ft.ScrollMode.HIDDEN)

    def _build_nav_item(self, icon, label, route, color="white"):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, color=color),
                    ft.Text(label, color=color, size=16),
                ],
                spacing=15,
            ),
            padding=15,
            border_radius=10,
            ink=True,
            on_click=lambda e: self.app.navigate(route),
            on_hover=lambda e: self._on_hover(e),
        )

    def _on_hover(self, e):
        e.control.bgcolor = "#3d4043" if e.data == "true" else None
        e.control.update()
