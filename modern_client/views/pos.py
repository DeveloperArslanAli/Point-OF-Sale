import flet as ft
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

from config import settings
from services.api import api_service
from components.barcode_scanner import BarcodeScannerInput, lookup_product_by_barcode

icons = ft.icons

class POSView(ft.Container):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 20
        
        self.cart_items = []
        self.products = []
        self.customers = []
        self.selected_customer = None
        self.shift_info = None
        self.drawer_info = None
        self.terminal_id = getattr(settings, "TERMINAL_ID", "POS-1")
        
        # Barcode scanner
        self.barcode_scanner = None
        
        # UI Components
        self.product_grid = ft.GridView(
            expand=True,
            runs_count=4,
            max_extent=250,
            child_aspect_ratio=0.75,
            spacing=20,
            run_spacing=20,
        )
        self.cart_list = ft.ListView(expand=True, spacing=10)
        self.total_text = ft.Text("$0.00", size=24, weight=ft.FontWeight.BOLD, color="white")
        self.customer_dropdown = ft.Dropdown(
            label="Select Customer",
            hint_text="Guest Customer",
            width=350,
            options=[],
            on_change=self._on_customer_change,
            bgcolor="#2d3033",
            color="white",
            border_color="#bb86fc",
            text_style=ft.TextStyle(color="white"),
        )
        
        self.content = self._build_layout()
        # Defer data loading to after mount or call explicitly
        # For now, we call it here, but in Flet it's often better to use did_mount
        self._load_data()

    def _build_layout(self):
        return ft.Row(
            [
                # Left: Products
                ft.Container(
                    expand=3,
                    content=ft.Column(
                        [
                            self._build_header(),
                            self.product_grid
                        ]
                    )
                ),
                # Right: Cart
                ft.Container(
                    width=400,
                    bgcolor="#1a1c1e",
                    border=ft.border.only(left=ft.border.BorderSide(1, "#2d3033")),
                    padding=20,
                    content=ft.Column(
                        [
                            ft.Text("Current Sale", size=24, weight=ft.FontWeight.BOLD, color="white"),
                            ft.Container(height=10),
                            self._cashier_logout_button(),
                            ft.Container(height=5),
                            self.customer_dropdown,
                            ft.Divider(color="#2d3033"),
                            self.cart_list,
                            ft.Divider(color="#2d3033"),
                            ft.Row([ft.Text("Total", color="grey"), self.total_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Container(height=10),
                            ft.ElevatedButton(
                                "Checkout",
                                bgcolor="#bb86fc",
                                color="black",
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                                height=50,
                                width=float("inf"),
                                on_click=self._checkout
                            )
                        ]
                    )
                )
            ],
            expand=True
        )

    def _cashier_logout_button(self):
        if self.app.user_role != "CASHIER":
            return ft.Container()
        return ft.ElevatedButton(
            "Logout",
            icon=icons.LOGOUT,
            bgcolor="#cf6679",
            color="white",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: self.app.navigate("logout"),
            tooltip="Logout",
        )

    def _build_header(self):
        # Barcode scanner input
        self.barcode_scanner = BarcodeScannerInput(
            on_scan=self._on_barcode_scan,
            hint_text="Scan barcode or search products...",
        )
        
        controls = [
            self.barcode_scanner,
            ft.IconButton(icons.FILTER_LIST, icon_color="white", tooltip="Filter"),
            ft.IconButton(icons.REFRESH, icon_color="white", tooltip="Refresh", on_click=lambda e: self._load_data()),
            ft.Container(expand=True),
            self._build_shift_badge(),
            self._build_drawer_badge(),
            ft.IconButton(icons.POINT_OF_SALE, icon_color="#bb86fc", tooltip="Start/End Shift", on_click=self._toggle_shift),
            ft.IconButton(icons.CALENDAR_MONTH, icon_color="#bb86fc", tooltip="Open/Close Drawer", on_click=self._toggle_drawer),
            ft.IconButton(icons.ATTACH_MONEY, icon_color="#bb86fc", tooltip="Record Cash Movement", on_click=self._record_cash_movement_dialog),
        ]

        if self.app.user_role == "CASHIER":
            controls.append(
                ft.TextButton(
                    "Logout",
                    icon=icons.LOGOUT,
                    style=ft.ButtonStyle(color="#cf6679"),
                    tooltip="Logout",
                    on_click=lambda e: self.app.navigate("logout"),
                )
            )

        return ft.Row(controls)
    
    def _on_barcode_scan(self, barcode: str):
        """Handle barcode scan or manual SKU entry."""
        if not barcode:
            return
        
        # Look up product by barcode/SKU
        product = lookup_product_by_barcode(barcode, self.products)
        
        if product:
            self._add_to_cart(product)
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Text(f"Added: {product.get('name', 'Product')}"),
                        bgcolor="#4caf50",
                        duration=1500,
                    )
                )
        else:
            # Try searching by name
            matching = [p for p in self.products if barcode.lower() in p.get("name", "").lower()]
            
            if len(matching) == 1:
                self._add_to_cart(matching[0])
                if self.page:
                    self.page.show_snack_bar(
                        ft.SnackBar(
                            content=ft.Text(f"Added: {matching[0].get('name', 'Product')}"),
                            bgcolor="#4caf50",
                            duration=1500,
                        )
                    )
            elif len(matching) > 1:
                # Filter product grid to matching items
                self._render_products(matching)
                if self.page:
                    self.page.show_snack_bar(
                        ft.SnackBar(
                            content=ft.Text(f"Found {len(matching)} matching products"),
                            bgcolor="#ff9800",
                            duration=2000,
                        )
                    )
            else:
                if self.page:
                    self.page.show_snack_bar(
                        ft.SnackBar(
                            content=ft.Text(f"Product not found: {barcode}"),
                            bgcolor="#f44336",
                            duration=2000,
                        )
                    )

    def _load_data(self):
        # Only load active products for POS
        self.products = api_service.get_products(active=True)
        self.customers = api_service.get_customers()
        self.shift_info = api_service.get_active_shift()
        # Attempt to align drawer with terminal
        self.drawer_info = api_service.get_open_drawer_for_terminal(self.terminal_id)
        
        self._render_products(self.products)
        self._refresh_status_badges()
        
        self.customer_dropdown.options = [
            ft.dropdown.Option(key=c["id"], text=f"{c['first_name']} {c['last_name']}")
            for c in self.customers
        ]
        if self.page:
            self.page.update()

    def _render_products(self, products):
        self.product_grid.controls = [self._build_product_card(p) for p in products]
        if self.page:
            self.product_grid.update()

    def _build_product_card(self, product):
        name = product.get("name", "Unknown")
        price = float(product.get("retail_price", 0))
        stock = int(product.get("stock_quantity", 0))
        is_out_of_stock = stock <= 0
        
        color = "#bb86fc" if not is_out_of_stock else "#cf6679"
        
        return ft.Container(
            bgcolor="#2d3033",
            border_radius=15,
            padding=15,
            ink=not is_out_of_stock,
            on_click=lambda e: self._add_to_cart(product) if not is_out_of_stock else None,
            opacity=0.5 if is_out_of_stock else 1.0,
            content=ft.Column(
                [
                    ft.Container(
                        height=100,
                        border_radius=10,
                        bgcolor=color, 
                        alignment=ft.alignment.center,
                        content=ft.Icon(icons.SHOPPING_BAG if not is_out_of_stock else icons.BLOCK, color="white", size=40)
                    ),
                    ft.Text(name, size=16, weight=ft.FontWeight.BOLD, color="white", no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"Stock: {stock}", size=12, color="grey"),
                    ft.Row(
                        [
                            ft.Text(f"${price:.2f}", size=14, color="#bb86fc", weight=ft.FontWeight.BOLD),
                            ft.Container(
                                bgcolor="#bb86fc" if not is_out_of_stock else "grey",
                                border_radius=50,
                                padding=5,
                                content=ft.Icon(icons.ADD, size=16, color="black")
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )
        )

    def _add_to_cart(self, product):
        stock = int(product.get("stock_quantity", 0))
        price = float(product.get("retail_price", 0))
        existing = next((item for item in self.cart_items if item["id"] == product["id"]), None)
        
        current_qty = existing["qty"] if existing else 0
        if current_qty + 1 > stock:
             if self.page:
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text(f"Cannot add more. Only {stock} in stock.")))
             return

        if existing:
            existing["qty"] += 1
        else:
            self.cart_items.append({
                "id": product["id"],
                "name": product.get("name", "Unknown"),
                "price": price,
                "qty": 1
            })
        
        self._update_cart_ui()

    def _update_cart_ui(self):
        self.cart_list.controls = [self._build_cart_item(item) for item in self.cart_items]
        total = sum(item["price"] * item["qty"] for item in self.cart_items)
        self.total_text.value = f"${total:.2f}"
        if self.page:
            self.cart_list.update()
            self.total_text.update()

    def _build_cart_item(self, item):
        return ft.Container(
            bgcolor="#2d3033",
            padding=10,
            border_radius=10,
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(item["name"], color="white", weight=ft.FontWeight.BOLD, width=150, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(f"${item['price']:.2f}", color="grey", size=12),
                        ],
                    ),
                    ft.Row(
                        [
                            ft.IconButton(icons.REMOVE, icon_size=16, icon_color="white", on_click=lambda e: self._update_qty(item, -1)),
                            ft.Text(str(item["qty"]), color="white"),
                            ft.IconButton(icons.ADD, icon_size=16, icon_color="white", on_click=lambda e: self._update_qty(item, 1)),
                        ],
                        spacing=0
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )
        )

    def _update_qty(self, item, change):
        item["qty"] += change
        if item["qty"] <= 0:
            self.cart_items.remove(item)
        self._update_cart_ui()

    def _on_customer_change(self, e):
        self.selected_customer = e.control.value

    def _refresh_status_badges(self):
        if self.page:
            if hasattr(self, "shift_badge"):
                status = "Active" if self.shift_info else "No Shift"
                color = "#4caf50" if self.shift_info else "#cf6679"
                self.shift_badge.content = ft.Text(f"Shift: {status}", color="black")
                self.shift_badge.bgcolor = color
                self.shift_badge.update()
            if hasattr(self, "drawer_badge"):
                status = "Open" if self.drawer_info else "Closed"
                color = "#4caf50" if self.drawer_info else "#cf6679"
                self.drawer_badge.content = ft.Text(f"Drawer: {status}", color="black")
                self.drawer_badge.bgcolor = color
                self.drawer_badge.update()

    def _build_shift_badge(self):
        self.shift_badge = ft.Container(
            content=ft.Text("Shift: -", color="black"),
            bgcolor="#2d3033",
            padding=8,
            border_radius=8,
        )
        return self.shift_badge

    def _build_drawer_badge(self):
        self.drawer_badge = ft.Container(
            content=ft.Text("Drawer: -", color="black"),
            bgcolor="#2d3033",
            padding=8,
            border_radius=8,
        )
        return self.drawer_badge

    def _toggle_shift(self, e=None):
        if self.shift_info:
            self._end_shift_dialog()
        else:
            self._start_shift_dialog()

    def _start_shift_dialog(self):
        opening_cash = ft.TextField(label="Opening Cash", value="0", keyboard_type=ft.KeyboardType.NUMBER, bgcolor="#2d3033", color="white")

        def do_start(ev):
            try:
                amount = float(opening_cash.value or 0)
            except ValueError:
                amount = 0
            self.shift_info = api_service.start_shift(self.terminal_id, opening_cash=amount)
            self._refresh_status_badges()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Shift started")))
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Start Shift"),
            content=opening_cash,
            actions=[ft.TextButton("Cancel", on_click=lambda ev: setattr(dialog, "open", False)), ft.ElevatedButton("Start", on_click=do_start)],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _end_shift_dialog(self):
        closing_cash = ft.TextField(label="Closing Cash", value="0", keyboard_type=ft.KeyboardType.NUMBER, bgcolor="#2d3033", color="white")

        def do_end(ev):
            try:
                amount = float(closing_cash.value or 0)
            except ValueError:
                amount = None
            if self.shift_info:
                self.shift_info = api_service.end_shift(self.shift_info.get("id"), closing_cash=amount)
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Shift ended")))
            self._refresh_status_badges()
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("End Shift"),
            content=closing_cash,
            actions=[ft.TextButton("Cancel", on_click=lambda ev: setattr(dialog, "open", False)), ft.ElevatedButton("End", on_click=do_end)],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _toggle_drawer(self, e=None):
        if self.drawer_info:
            self._close_drawer_dialog()
        else:
            self._open_drawer_dialog()

    def _open_drawer_dialog(self):
        opening_amount = ft.TextField(label="Opening Float", value="0", keyboard_type=ft.KeyboardType.NUMBER, bgcolor="#2d3033", color="white")

        def do_open(ev):
            try:
                amount = float(opening_amount.value or 0)
            except ValueError:
                amount = 0
            self.drawer_info = api_service.open_cash_drawer(self.terminal_id, opening_amount=amount)
            self._refresh_status_badges()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Drawer opened")))
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Open Drawer"),
            content=opening_amount,
            actions=[ft.TextButton("Cancel", on_click=lambda ev: setattr(dialog, "open", False)), ft.ElevatedButton("Open", on_click=do_open)],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _close_drawer_dialog(self):
        closing_amount = ft.TextField(label="Closing Count", value="0", keyboard_type=ft.KeyboardType.NUMBER, bgcolor="#2d3033", color="white")
        notes_field = ft.TextField(label="Notes", bgcolor="#2d3033", color="white")

        def do_close(ev):
            try:
                amount = float(closing_amount.value or 0)
            except ValueError:
                amount = 0
            if self.drawer_info:
                self.drawer_info = api_service.close_cash_drawer(self.drawer_info.get("id"), closing_amount=amount, notes=notes_field.value or None)
            self._refresh_status_badges()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Drawer closed")))
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Close Drawer"),
            content=ft.Column([closing_amount, notes_field], tight=True, width=300),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: setattr(dialog, "open", False)), ft.ElevatedButton("Close", on_click=do_close)],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _record_cash_movement_dialog(self):
        if not self.drawer_info:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Open a drawer first")))
            return
        movement_type = ft.Dropdown(options=[
            ft.dropdown.Option("pay_in"),
            ft.dropdown.Option("payout"),
            ft.dropdown.Option("drop"),
            ft.dropdown.Option("pickup"),
        ], value="pay_in", bgcolor="#2d3033", color="white")
        amount_field = ft.TextField(label="Amount", value="0", keyboard_type=ft.KeyboardType.NUMBER, bgcolor="#2d3033", color="white")
        notes_field = ft.TextField(label="Notes", bgcolor="#2d3033", color="white")

        def do_record(ev):
            try:
                amount = float(amount_field.value or 0)
            except ValueError:
                amount = 0
            api_service.record_cash_movement(self.drawer_info.get("id"), movement_type.value, amount, notes_field.value or None)
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Movement recorded")))
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Record Cash Movement"),
            content=ft.Column([movement_type, amount_field, notes_field], tight=True, width=320),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: setattr(dialog, "open", False)), ft.ElevatedButton("Record", on_click=do_record)],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _checkout(self, e):
        if not self.cart_items:
            return
            
        total_amount = sum(item["price"] * item["qty"] for item in self.cart_items)
        cart_snapshot = [item.copy() for item in self.cart_items]

        sale_data = {
            "customer_id": self.selected_customer,
            "currency": "USD",
            "lines": [
                {
                    "product_id": item["id"],
                    "quantity": item["qty"],
                    "unit_price": item["price"]
                }
                for item in self.cart_items
            ],
            "payments": [
                {
                    "payment_method": "cash",
                    "amount": round(total_amount, 2)
                }
            ]
        }
        
        result = api_service.create_sale(sale_data)
        if result:
            sale = result.get("sale") or {}
            sale_id = sale.get("id")
            sale_total = float(sale.get("total_amount", total_amount))
            fallback_receipt = {
                "number": sale_id or "Sale",
                "lines": [
                    {"name": item.get("name", "Item"), "quantity": item.get("qty", 1), "unit_price": item.get("price", 0)}
                    for item in cart_snapshot
                ],
                "total_amount": sale_total,
            }

            if sale_id:
                api_service.record_cash_payment(sale_id, sale_total)
            receipts = api_service.get_receipts_for_sale(sale_id) if sale_id else None
            if receipts:
                self._show_receipt_dialog(receipts)
            else:
                self._show_receipt_dialog(fallback_receipt)

            self.cart_items = []
            self._update_cart_ui()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Sale recorded successfully!")))
        else:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Failed to record sale.")))

    def _show_receipt_dialog(self, receipts):
        # receipts may be dict or list depending on API response; handle first receipt
        receipt = None
        if isinstance(receipts, list) and receipts:
            receipt = receipts[0]
        elif isinstance(receipts, dict):
            # Could be {items:[...]}
            if "items" in receipts and isinstance(receipts["items"], list) and receipts["items"]:
                receipt = receipts["items"][0]
            else:
                receipt = receipts

        if not receipt:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("No receipt data available")))
            return

        lines = receipt.get("lines", []) or receipt.get("items", []) or []
        total = receipt.get("total_amount") or receipt.get("amount") or 0
        receipt_no = receipt.get("number") or receipt.get("id") or "Receipt"

        def line_to_text(line: dict) -> str:
            name = line.get("name") or line.get("product_name") or "Item"
            qty = line.get("quantity", 1)
            price = line.get("unit_price", line.get("price", 0))
            return f"{name} - {qty} x ${price}"

        line_text = "\n".join(line_to_text(line) for line in lines) or "No line items"
        header = f"Receipt: {receipt_no}\nTotal: ${total}"
        receipt_text = f"{header}\n{line_text}"

        content = ft.Column(
            [
                ft.Text(f"Receipt: {receipt_no}", weight=ft.FontWeight.BOLD),
                ft.Text(f"Total: ${total}"),
                ft.Text(line_text, selectable=True),
            ],
            tight=True,
            spacing=8,
        )

        def close_dialog(ev=None):
            dialog.open = False
            self.page.update()

        def copy_dialog(ev=None):
            try:
                self.page.set_clipboard(receipt_text)
                self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Receipt copied")))
            except Exception:
                pass

        def print_dialog(ev=None):
            html = self._build_receipt_html(receipt_no, lines, total)
            self._launch_print_preview(html)

        dialog = ft.AlertDialog(
            title=ft.Text("Receipt"),
            content=content,
            actions=[
                ft.TextButton("Copy", on_click=copy_dialog),
                ft.TextButton("Print", on_click=print_dialog),
                ft.TextButton("Close", on_click=close_dialog),
            ],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _build_receipt_html(self, receipt_no: str, lines: list[dict], total: float) -> str:
        rows = "".join(
            f"<tr><td>{(line.get('name') or line.get('product_name') or 'Item')}</td><td style='text-align:center'>{line.get('quantity',1)}</td><td style='text-align:right'>${line.get('unit_price', line.get('price', 0))}</td></tr>"
            for line in lines
        )
        total_display = f"{float(total):.2f}" if total is not None else "0.00"
        body = f"""
<!doctype html><html><head><meta charset='utf-8'><title>Receipt {receipt_no}</title>
<style>
body {{ font-family: Arial, sans-serif; padding: 24px; }}
h2 {{ margin: 0 0 12px 0; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
td {{ padding: 6px 0; border-bottom: 1px solid #ddd; }}
.total {{ font-weight: bold; text-align: right; margin-top: 16px; }}
</style></head><body>
<h2>Receipt {receipt_no}</h2>
<table><tbody>{rows}</tbody></table>
<div class='total'>Total: ${total_display}</div>
<script>window.onload = () => {{ window.print(); }}</script>
</body></html>
"""
        return body.replace("\n", "")

    def _launch_print_preview(self, html: str) -> None:
        """Open HTML in the system default browser for printing. Uses a temp file if data URLs are blocked."""
        # Try data URL first (works in browser view)
        try:
            encoded = quote(html, safe="")
            self.page.launch_url(f"data:text/html,{encoded}")
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Opening print preview..."), duration=1500))
            return
        except Exception as exc:
            print(f"Data URL print failed: {exc}")

        # Fallback to temp file to ensure desktop print works
        try:
            with NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as tmp:
                tmp.write(html)
                tmp_path = Path(tmp.name)
            uri = tmp_path.as_uri()
            self.page.launch_url(uri)
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text(f"Print preview opened: {tmp_path}"), duration=3000))
        except Exception as exc:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text(f"Unable to launch print preview: {exc}")))
            print(f"Print preview failed: {exc}")
