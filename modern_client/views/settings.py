"""Settings view for Admin POS client.

Provides configuration management for:
- Company branding (logo, colors, company info)
- Currency and number formatting
- Tax configuration
- Invoice/Receipt settings
- Theme preferences
"""

import flet as ft
from services.api import api_service

icons = ft.icons


class SettingsView(ft.Container):
    """Settings management view."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 20
        self.settings_data = {}
        self.currencies = []
        self.timezones = []
        
        # Build UI
        self.content = self._build_layout()

    def did_mount(self):
        """Load settings when view is mounted."""
        self._load_settings()

    def _build_layout(self):
        """Build the main settings layout."""
        # Tab navigation
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            tabs=[
                ft.Tab(text="Branding", icon=icons.BRUSH),
                ft.Tab(text="Currency", icon=icons.ATTACH_MONEY),
                ft.Tab(text="Tax", icon=icons.RECEIPT_LONG),
                ft.Tab(text="Invoice", icon=icons.DESCRIPTION),
                ft.Tab(text="Theme", icon=icons.PALETTE),
            ],
            on_change=self._on_tab_change,
            expand=True,
        )
        
        # Content container that switches based on tab
        self.content_container = ft.Container(
            expand=True,
            padding=20,
            content=self._build_branding_section(),
        )
        
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Settings", size=30, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icons.REFRESH,
                            icon_color="white",
                            tooltip="Refresh",
                            on_click=lambda e: self._load_settings(),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(color="#2d3033"),
                self.tabs,
                self.content_container,
            ],
            expand=True,
        )

    def _on_tab_change(self, e):
        """Handle tab change."""
        index = e.control.selected_index
        
        sections = [
            self._build_branding_section,
            self._build_currency_section,
            self._build_tax_section,
            self._build_invoice_section,
            self._build_theme_section,
        ]
        
        self.content_container.content = sections[index]()
        self.update()

    def _load_settings(self):
        """Load settings from API."""
        try:
            settings = api_service.get_settings()
            if settings:
                self.settings_data = settings
                
            # Load currencies
            currencies = api_service.get_currencies()
            if currencies:
                self.currencies = currencies
                
            # Load timezones
            timezones = api_service.get_timezones()
            if timezones:
                self.timezones = timezones
                
            # Refresh current tab
            self._on_tab_change(type("obj", (object,), {"control": self.tabs})())
            
        except Exception as e:
            print(f"Error loading settings: {e}")
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Text(f"Error loading settings: {e}"),
                        bgcolor="#f44336",
                    )
                )

    # ===================
    # Branding Section
    # ===================

    def _build_branding_section(self):
        """Build the branding configuration section."""
        branding = self.settings_data.get("branding", {})
        
        # Company info fields
        self.company_name = ft.TextField(
            label="Company Name",
            value=branding.get("company_name", ""),
            width=400,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.company_tagline = ft.TextField(
            label="Tagline",
            value=branding.get("company_tagline", "") or "",
            width=400,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.company_address = ft.TextField(
            label="Address",
            value=branding.get("company_address", "") or "",
            width=400,
            multiline=True,
            min_lines=2,
            max_lines=4,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.company_phone = ft.TextField(
            label="Phone",
            value=branding.get("company_phone", "") or "",
            width=200,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.company_email = ft.TextField(
            label="Email",
            value=branding.get("company_email", "") or "",
            width=200,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.company_website = ft.TextField(
            label="Website",
            value=branding.get("company_website", "") or "",
            width=400,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.tax_registration = ft.TextField(
            label="Tax Registration Number",
            value=branding.get("tax_registration_number", "") or "",
            width=200,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.business_registration = ft.TextField(
            label="Business Registration Number",
            value=branding.get("business_registration_number", "") or "",
            width=200,
            bgcolor="#2d3033",
            color="white",
        )
        
        # Color pickers (using text fields with hex validation)
        self.primary_color = ft.TextField(
            label="Primary Color",
            value=branding.get("primary_color", "#6366f1"),
            width=150,
            bgcolor="#2d3033",
            color="white",
            prefix_icon=icons.COLOR_LENS,
        )
        
        self.secondary_color = ft.TextField(
            label="Secondary Color",
            value=branding.get("secondary_color", "#8b5cf6"),
            width=150,
            bgcolor="#2d3033",
            color="white",
            prefix_icon=icons.COLOR_LENS,
        )
        
        self.accent_color = ft.TextField(
            label="Accent Color",
            value=branding.get("accent_color", "#bb86fc"),
            width=150,
            bgcolor="#2d3033",
            color="white",
            prefix_icon=icons.COLOR_LENS,
        )
        
        # Logo preview
        logo_url = branding.get("logo_url")
        logo_content = ft.Container(
            width=200,
            height=100,
            bgcolor="#1a1c1e",
            border=ft.border.all(1, "#3d4043"),
            border_radius=10,
            alignment=ft.alignment.center,
            content=ft.Image(src=logo_url, width=180, height=80, fit=ft.ImageFit.CONTAIN)
            if logo_url
            else ft.Text("No Logo", color="grey"),
        )
        
        return ft.Column(
            [
                ft.Text("Company Information", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                ft.Row([self.company_name, self.company_tagline], spacing=20),
                ft.Container(height=10),
                self.company_address,
                ft.Container(height=10),
                ft.Row([self.company_phone, self.company_email], spacing=20),
                ft.Container(height=10),
                self.company_website,
                ft.Container(height=10),
                ft.Row([self.tax_registration, self.business_registration], spacing=20),
                ft.Divider(color="#3d4043", height=30),
                ft.Text("Brand Colors", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                ft.Row(
                    [self.primary_color, self.secondary_color, self.accent_color],
                    spacing=20,
                ),
                ft.Container(height=10),
                ft.Row(
                    [
                        self._color_preview("Primary", branding.get("primary_color", "#6366f1")),
                        self._color_preview("Secondary", branding.get("secondary_color", "#8b5cf6")),
                        self._color_preview("Accent", branding.get("accent_color", "#bb86fc")),
                    ],
                    spacing=20,
                ),
                ft.Divider(color="#3d4043", height=30),
                ft.Text("Logo", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                ft.Row([logo_content, ft.ElevatedButton("Upload Logo", icon=icons.UPLOAD, on_click=self._upload_logo)]),
                ft.Container(height=30),
                ft.ElevatedButton(
                    "Save Branding",
                    icon=icons.SAVE,
                    bgcolor="#6366f1",
                    color="white",
                    on_click=self._save_branding,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def _color_preview(self, label: str, color: str):
        """Create a color preview box."""
        return ft.Container(
            width=100,
            height=50,
            bgcolor=color,
            border_radius=8,
            alignment=ft.alignment.center,
            content=ft.Text(label, color="white", size=12, weight=ft.FontWeight.BOLD),
        )

    def _upload_logo(self, e):
        """Handle logo upload."""
        # In Flet, file upload requires FilePicker
        if self.page:
            self.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("Logo upload: Please provide a URL for now"),
                    bgcolor="#ff9800",
                )
            )

    def _save_branding(self, e):
        """Save branding settings."""
        try:
            result = api_service.update_branding({
                "company_name": self.company_name.value,
                "company_tagline": self.company_tagline.value or None,
                "company_address": self.company_address.value or None,
                "company_phone": self.company_phone.value or None,
                "company_email": self.company_email.value or None,
                "company_website": self.company_website.value or None,
                "tax_registration_number": self.tax_registration.value or None,
                "business_registration_number": self.business_registration.value or None,
                "primary_color": self.primary_color.value,
                "secondary_color": self.secondary_color.value,
                "accent_color": self.accent_color.value,
            })
            
            if result:
                self.settings_data = result
                if self.page:
                    self.page.show_snack_bar(
                        ft.SnackBar(content=ft.Text("Branding saved successfully!"), bgcolor="#4caf50")
                    )
        except Exception as ex:
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"Error saving: {ex}"), bgcolor="#f44336")
                )

    # ===================
    # Currency Section
    # ===================

    def _build_currency_section(self):
        """Build the currency configuration section."""
        currency = self.settings_data.get("currency", {})
        
        # Currency dropdown
        currency_options = [
            ft.dropdown.Option(key=c["code"], text=f"{c['code']} - {c['name']} ({c['symbol']})")
            for c in self.currencies
        ] if self.currencies else [ft.dropdown.Option(key="USD", text="USD - US Dollar ($)")]
        
        self.currency_dropdown = ft.Dropdown(
            label="Currency",
            value=currency.get("currency_code", "USD"),
            options=currency_options,
            width=300,
            bgcolor="#2d3033",
            on_change=self._on_currency_change,
        )
        
        self.currency_symbol = ft.TextField(
            label="Symbol",
            value=currency.get("currency_symbol", "$"),
            width=80,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.currency_position = ft.Dropdown(
            label="Symbol Position",
            value=currency.get("currency_position", "before"),
            options=[
                ft.dropdown.Option(key="before", text="Before ($100)"),
                ft.dropdown.Option(key="after", text="After (100$)"),
            ],
            width=200,
            bgcolor="#2d3033",
        )
        
        self.decimal_places = ft.Dropdown(
            label="Decimal Places",
            value=str(currency.get("decimal_places", 2)),
            options=[
                ft.dropdown.Option(key="0", text="0 (100)"),
                ft.dropdown.Option(key="2", text="2 (100.00)"),
                ft.dropdown.Option(key="3", text="3 (100.000)"),
            ],
            width=150,
            bgcolor="#2d3033",
        )
        
        self.thousand_separator = ft.Dropdown(
            label="Thousand Separator",
            value=currency.get("thousand_separator", ","),
            options=[
                ft.dropdown.Option(key=",", text="Comma (1,000)"),
                ft.dropdown.Option(key=".", text="Period (1.000)"),
                ft.dropdown.Option(key=" ", text="Space (1 000)"),
                ft.dropdown.Option(key="'", text="Apostrophe (1'000)"),
            ],
            width=200,
            bgcolor="#2d3033",
        )
        
        self.decimal_separator = ft.Dropdown(
            label="Decimal Separator",
            value=currency.get("decimal_separator", "."),
            options=[
                ft.dropdown.Option(key=".", text="Period (100.00)"),
                ft.dropdown.Option(key=",", text="Comma (100,00)"),
            ],
            width=200,
            bgcolor="#2d3033",
        )
        
        # Preview
        self.currency_preview = ft.Text(
            self._format_preview_amount(currency),
            size=24,
            weight=ft.FontWeight.BOLD,
            color="#bb86fc",
        )
        
        return ft.Column(
            [
                ft.Text("Currency Settings", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                ft.Row([self.currency_dropdown, self.currency_symbol], spacing=20),
                ft.Container(height=10),
                ft.Row([self.currency_position, self.decimal_places], spacing=20),
                ft.Container(height=10),
                ft.Row([self.thousand_separator, self.decimal_separator], spacing=20),
                ft.Divider(color="#3d4043", height=30),
                ft.Text("Preview", size=16, weight=ft.FontWeight.BOLD, color="grey"),
                self.currency_preview,
                ft.Container(height=30),
                ft.ElevatedButton(
                    "Save Currency Settings",
                    icon=icons.SAVE,
                    bgcolor="#6366f1",
                    color="white",
                    on_click=self._save_currency,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def _format_preview_amount(self, currency: dict) -> str:
        """Format a preview amount based on current settings."""
        amount = 1234567.89
        symbol = currency.get("currency_symbol", "$")
        position = currency.get("currency_position", "before")
        decimals = currency.get("decimal_places", 2)
        thousand_sep = currency.get("thousand_separator", ",")
        decimal_sep = currency.get("decimal_separator", ".")
        
        # Format the number
        formatted = f"{amount:,.{decimals}f}"
        
        # Replace separators
        if thousand_sep != ",":
            formatted = formatted.replace(",", "TEMP")
        if decimal_sep != ".":
            formatted = formatted.replace(".", decimal_sep)
        if thousand_sep != ",":
            formatted = formatted.replace("TEMP", thousand_sep)
        
        # Add symbol
        if position == "before":
            return f"{symbol}{formatted}"
        else:
            return f"{formatted}{symbol}"

    def _on_currency_change(self, e):
        """Handle currency selection change."""
        code = e.control.value
        # Find symbol for selected currency
        for c in self.currencies:
            if c["code"] == code:
                self.currency_symbol.value = c["symbol"]
                break
        self.update()

    def _save_currency(self, e):
        """Save currency settings."""
        try:
            result = api_service.update_currency({
                "currency_code": self.currency_dropdown.value,
                "currency_symbol": self.currency_symbol.value,
                "currency_position": self.currency_position.value,
                "decimal_places": int(self.decimal_places.value),
                "thousand_separator": self.thousand_separator.value,
                "decimal_separator": self.decimal_separator.value,
            })
            
            if result:
                self.settings_data = result
                if self.page:
                    self.page.show_snack_bar(
                        ft.SnackBar(content=ft.Text("Currency settings saved!"), bgcolor="#4caf50")
                    )
        except Exception as ex:
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"Error saving: {ex}"), bgcolor="#f44336")
                )

    # ===================
    # Tax Section
    # ===================

    def _build_tax_section(self):
        """Build the tax configuration section."""
        tax = self.settings_data.get("tax", {})
        
        self.default_tax_rate = ft.TextField(
            label="Default Tax Rate (%)",
            value=str(float(tax.get("default_tax_rate", 0)) * 100),
            width=150,
            bgcolor="#2d3033",
            color="white",
            suffix_text="%",
        )
        
        self.tax_inclusive = ft.Switch(
            label="Tax Inclusive Pricing",
            value=tax.get("tax_inclusive_pricing", False),
            active_color="#6366f1",
        )
        
        self.show_tax_breakdown = ft.Switch(
            label="Show Tax Breakdown on Receipts",
            value=tax.get("show_tax_breakdown", True),
            active_color="#6366f1",
        )
        
        # Tax rates table
        tax_rates = tax.get("tax_rates", [])
        self.tax_rates_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Name", color="white")),
                ft.DataColumn(ft.Text("Rate", color="white")),
                ft.DataColumn(ft.Text("Default", color="white")),
                ft.DataColumn(ft.Text("Actions", color="white")),
            ],
            rows=[
                self._tax_rate_row(rate) for rate in tax_rates
            ],
        )
        
        return ft.Column(
            [
                ft.Text("Tax Configuration", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                self.default_tax_rate,
                ft.Container(height=10),
                self.tax_inclusive,
                ft.Container(height=10),
                self.show_tax_breakdown,
                ft.Divider(color="#3d4043", height=30),
                ft.Row(
                    [
                        ft.Text("Tax Rates", size=16, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            "Add Tax Rate",
                            icon=icons.ADD,
                            on_click=self._add_tax_rate_dialog,
                        ),
                    ],
                ),
                ft.Container(height=10),
                self.tax_rates_table,
                ft.Container(height=30),
                ft.ElevatedButton(
                    "Save Tax Settings",
                    icon=icons.SAVE,
                    bgcolor="#6366f1",
                    color="white",
                    on_click=self._save_tax,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def _tax_rate_row(self, rate: dict):
        """Create a tax rate table row."""
        return ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(rate.get("name", ""), color="white")),
                ft.DataCell(ft.Text(f"{float(rate.get('rate', 0)) * 100:.2f}%", color="white")),
                ft.DataCell(ft.Icon(icons.CHECK if rate.get("is_default") else icons.CLOSE, color="grey")),
                ft.DataCell(
                    ft.IconButton(icons.DELETE, icon_color="#cf6679", tooltip="Remove"),
                ),
            ],
        )

    def _add_tax_rate_dialog(self, e):
        """Show dialog to add a new tax rate."""
        if self.page:
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text("Tax rate dialog coming soon"), bgcolor="#ff9800")
            )

    def _save_tax(self, e):
        """Save tax settings."""
        try:
            # Convert percentage to decimal
            rate_percent = float(self.default_tax_rate.value or 0)
            rate_decimal = rate_percent / 100
            
            result = api_service.update_tax({
                "default_tax_rate": rate_decimal,
                "tax_inclusive_pricing": self.tax_inclusive.value,
                "show_tax_breakdown": self.show_tax_breakdown.value,
            })
            
            if result:
                self.settings_data = result
                if self.page:
                    self.page.show_snack_bar(
                        ft.SnackBar(content=ft.Text("Tax settings saved!"), bgcolor="#4caf50")
                    )
        except Exception as ex:
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"Error saving: {ex}"), bgcolor="#f44336")
                )

    # ===================
    # Invoice Section
    # ===================

    def _build_invoice_section(self):
        """Build the invoice/receipt configuration section."""
        invoice = self.settings_data.get("invoice", {})
        
        self.invoice_prefix = ft.TextField(
            label="Invoice Prefix",
            value=invoice.get("invoice_prefix", "INV"),
            width=100,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.receipt_footer = ft.TextField(
            label="Receipt Footer Message",
            value=invoice.get("receipt_footer_message", "Thank you for your business!"),
            width=400,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.invoice_header = ft.TextField(
            label="Invoice Header Text",
            value=invoice.get("invoice_header_text", "") or "",
            width=400,
            multiline=True,
            min_lines=2,
            max_lines=4,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.invoice_footer = ft.TextField(
            label="Invoice Footer Text",
            value=invoice.get("invoice_footer_text", "") or "",
            width=400,
            multiline=True,
            min_lines=2,
            max_lines=4,
            bgcolor="#2d3033",
            color="white",
        )
        
        self.show_logo_receipt = ft.Switch(
            label="Show Logo on Receipt",
            value=invoice.get("show_logo_on_receipt", True),
            active_color="#6366f1",
        )
        
        self.show_logo_invoice = ft.Switch(
            label="Show Logo on Invoice",
            value=invoice.get("show_logo_on_invoice", True),
            active_color="#6366f1",
        )
        
        self.terms = ft.TextField(
            label="Terms & Conditions",
            value=invoice.get("terms_and_conditions", "") or "",
            width=500,
            multiline=True,
            min_lines=3,
            max_lines=6,
            bgcolor="#2d3033",
            color="white",
        )
        
        return ft.Column(
            [
                ft.Text("Invoice & Receipt Settings", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                ft.Row([self.invoice_prefix], spacing=20),
                ft.Container(height=10),
                self.receipt_footer,
                ft.Divider(color="#3d4043", height=30),
                ft.Text("Invoice Content", size=16, weight=ft.FontWeight.BOLD, color="grey"),
                ft.Container(height=10),
                self.invoice_header,
                ft.Container(height=10),
                self.invoice_footer,
                ft.Container(height=10),
                ft.Row([self.show_logo_receipt, self.show_logo_invoice], spacing=30),
                ft.Container(height=10),
                self.terms,
                ft.Container(height=30),
                ft.ElevatedButton(
                    "Save Invoice Settings",
                    icon=icons.SAVE,
                    bgcolor="#6366f1",
                    color="white",
                    on_click=self._save_invoice,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def _save_invoice(self, e):
        """Save invoice settings."""
        try:
            # Build full settings update
            full_update = {
                "invoice": {
                    "invoice_prefix": self.invoice_prefix.value,
                    "invoice_number_length": 6,
                    "invoice_header_text": self.invoice_header.value or None,
                    "invoice_footer_text": self.invoice_footer.value or None,
                    "receipt_footer_message": self.receipt_footer.value,
                    "show_logo_on_receipt": self.show_logo_receipt.value,
                    "show_logo_on_invoice": self.show_logo_invoice.value,
                    "show_tax_breakdown": True,
                    "show_payment_instructions": False,
                    "payment_instructions": None,
                    "terms_and_conditions": self.terms.value or None,
                }
            }
            
            result = api_service.update_settings(full_update)
            
            if result:
                self.settings_data = result
                if self.page:
                    self.page.show_snack_bar(
                        ft.SnackBar(content=ft.Text("Invoice settings saved!"), bgcolor="#4caf50")
                    )
        except Exception as ex:
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"Error saving: {ex}"), bgcolor="#f44336")
                )

    # ===================
    # Theme Section
    # ===================

    def _build_theme_section(self):
        """Build the theme configuration section."""
        theme = self.settings_data.get("theme", {})
        
        self.theme_mode = ft.RadioGroup(
            value=theme.get("mode", "dark"),
            content=ft.Row(
                [
                    ft.Radio(value="light", label="Light", fill_color="white"),
                    ft.Radio(value="dark", label="Dark", fill_color="white"),
                    ft.Radio(value="system", label="System", fill_color="white"),
                ],
                spacing=30,
            ),
        )
        
        self.font_family = ft.Dropdown(
            label="Font Family",
            value=theme.get("font_family", "Roboto"),
            options=[
                ft.dropdown.Option(key="Roboto", text="Roboto"),
                ft.dropdown.Option(key="Inter", text="Inter"),
                ft.dropdown.Option(key="Open Sans", text="Open Sans"),
                ft.dropdown.Option(key="Lato", text="Lato"),
                ft.dropdown.Option(key="Montserrat", text="Montserrat"),
            ],
            width=200,
            bgcolor="#2d3033",
        )
        
        self.border_radius = ft.Slider(
            min=0,
            max=30,
            divisions=30,
            value=theme.get("border_radius", 10),
            label="{value}px",
            active_color="#6366f1",
        )
        
        return ft.Column(
            [
                ft.Text("Theme Settings", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                ft.Text("Color Mode", size=14, color="grey"),
                self.theme_mode,
                ft.Container(height=20),
                self.font_family,
                ft.Container(height=20),
                ft.Text("Border Radius", size=14, color="grey"),
                self.border_radius,
                ft.Container(height=30),
                ft.ElevatedButton(
                    "Save Theme Settings",
                    icon=icons.SAVE,
                    bgcolor="#6366f1",
                    color="white",
                    on_click=self._save_theme,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def _save_theme(self, e):
        """Save theme settings."""
        try:
            result = api_service.update_theme({
                "mode": self.theme_mode.value,
                "font_family": self.font_family.value,
                "border_radius": int(self.border_radius.value),
            })
            
            if result:
                self.settings_data = result
                if self.page:
                    self.page.show_snack_bar(
                        ft.SnackBar(content=ft.Text("Theme settings saved!"), bgcolor="#4caf50")
                    )
        except Exception as ex:
            if self.page:
                self.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"Error saving: {ex}"), bgcolor="#f44336")
                )
