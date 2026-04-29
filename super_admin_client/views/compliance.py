"""Compliance view for PCI-DSS and GDPR oversight."""
import flet as ft

from config import config
from services.api_v2 import api_client
from components.badge import StatusBadge
from components.loading import LoadingIndicator


class ComplianceView(ft.Container):
    """Compliance dashboard for PCI-DSS and GDPR."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        
        self._build()
    
    def _build(self):
        """Build the compliance view layout."""
        # Tabs for different compliance areas
        self.tabs = ft.Tabs(
            selected_index=0,
            tabs=[
                ft.Tab(text="PCI-DSS", icon=ft.Icons.SECURITY),
                ft.Tab(text="GDPR", icon=ft.Icons.PRIVACY_TIP),
            ],
            on_change=self._on_tab_change,
        )
        
        # Content areas
        self.pci_content = self._build_pci_section()
        self.gdpr_content = self._build_gdpr_section()
        
        self.content_area = ft.Container(
            content=self.pci_content,
            expand=True,
        )
        
        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Compliance & Security Overview", color="grey"),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            "Run Compliance Check",
                            icon=ft.Icons.PLAY_ARROW,
                            bgcolor=config.PRIMARY_COLOR,
                            color="white",
                            on_click=self._run_compliance_check,
                        ),
                    ],
                ),
                ft.Container(height=10),
                self.tabs,
                ft.Container(height=20),
                self.content_area,
            ],
            expand=True,
        )
    
    def _build_pci_section(self):
        """Build the PCI-DSS compliance section."""
        self.pci_container = ft.Container(
            content=LoadingIndicator(message="Loading compliance data..."),
            expand=True,
        )
        
        return self.pci_container
    
    def _build_gdpr_section(self):
        """Build the GDPR section."""
        self.gdpr_container = ft.Container(
            content=LoadingIndicator(message="Loading GDPR data..."),
            expand=True,
        )
        
        return self.gdpr_container
    
    def _on_tab_change(self, e):
        """Handle tab change."""
        if e.control.selected_index == 0:
            self.content_area.content = self.pci_content
            self._load_pci()
        else:
            self.content_area.content = self.gdpr_content
            self._load_gdpr()
        self.update()
    
    def did_mount(self):
        """Load data on mount."""
        self._load_pci()
    
    def _run_compliance_check(self, e):
        """Run a new compliance check."""
        self._load_pci()
    
    def _load_pci(self):
        """Load PCI-DSS compliance data."""
        compliance = api_client.get_pci_compliance()
        
        if compliance and not compliance.get("error"):
            is_compliant = compliance.get("is_compliant", False)
            critical_issues = compliance.get("critical_issues", [])
            warnings = compliance.get("warnings", [])
            passed_checks = compliance.get("passed_checks", [])
            checked_at = compliance.get("checked_at", "Unknown")
            
            # Status banner
            if is_compliant:
                banner_color = config.SUCCESS_COLOR
                banner_icon = ft.Icons.VERIFIED
                banner_text = "PCI-DSS Compliant"
                banner_subtitle = "All security requirements are met"
            else:
                banner_color = config.ERROR_COLOR
                banner_icon = ft.Icons.GPPBAD
                banner_text = "PCI-DSS Non-Compliant"
                banner_subtitle = f"{len(critical_issues)} critical issues require attention"
            
            status_banner = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(banner_icon, color="white", size=48),
                        ft.Column(
                            [
                                ft.Text(
                                    banner_text,
                                    size=24,
                                    weight=ft.FontWeight.BOLD,
                                    color="white",
                                ),
                                ft.Text(banner_subtitle, color="white", size=14),
                            ],
                            spacing=5,
                        ),
                        ft.Container(expand=True),
                        ft.Column(
                            [
                                ft.Text("Last Checked", color="white", size=11),
                                ft.Text(
                                    checked_at[:10] if len(checked_at) > 10 else checked_at,
                                    color="white",
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                        ),
                    ],
                    spacing=20,
                ),
                bgcolor=banner_color,
                border_radius=12,
                padding=20,
            )
            
            # Summary cards
            summary_row = ft.Row(
                [
                    self._build_summary_card("Critical Issues", len(critical_issues), config.ERROR_COLOR),
                    self._build_summary_card("Warnings", len(warnings), config.WARNING_COLOR),
                    self._build_summary_card("Passed Checks", len(passed_checks), config.SUCCESS_COLOR),
                ],
                spacing=20,
            )
            
            # Issues list
            issues_section = ft.Column(
                [
                    ft.Text("Critical Issues", size=16, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Container(height=10),
                    self._build_issues_list(critical_issues, config.ERROR_COLOR, ft.Icons.ERROR) if critical_issues else
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.CHECK_CIRCLE, color=config.SUCCESS_COLOR),
                                ft.Text("No critical issues found", color=config.SUCCESS_COLOR),
                            ],
                            spacing=10,
                        ),
                        bgcolor=f"{config.SUCCESS_COLOR}20",
                        border_radius=8,
                        padding=15,
                    ),
                ],
            )
            
            warnings_section = ft.Column(
                [
                    ft.Text("Warnings", size=16, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Container(height=10),
                    self._build_issues_list(warnings, config.WARNING_COLOR, ft.Icons.WARNING) if warnings else
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.CHECK_CIRCLE, color=config.SUCCESS_COLOR),
                                ft.Text("No warnings", color=config.SUCCESS_COLOR),
                            ],
                            spacing=10,
                        ),
                        bgcolor=f"{config.SUCCESS_COLOR}20",
                        border_radius=8,
                        padding=15,
                    ),
                ],
            )
            
            passed_section = ft.ExpansionTile(
                title=ft.Text("Passed Checks", weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(f"{len(passed_checks)} checks passed"),
                initially_expanded=False,
                controls=[
                    self._build_issues_list(passed_checks, config.SUCCESS_COLOR, ft.Icons.CHECK_CIRCLE),
                ],
            )
            
            self.pci_container.content = ft.Column(
                [
                    status_banner,
                    ft.Container(height=20),
                    summary_row,
                    ft.Container(height=30),
                    issues_section,
                    ft.Container(height=20),
                    warnings_section,
                    ft.Container(height=20),
                    passed_section,
                ],
                scroll=ft.ScrollMode.AUTO,
            )
        else:
            self.pci_container.content = ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=64, color="grey"),
                    ft.Text("Unable to load compliance data", size=16, color="grey"),
                    ft.Text("Check API connection and try again", size=13, color="grey"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        
        self.update()
    
    def _build_summary_card(self, title: str, count: int, color: str) -> ft.Container:
        """Build a summary stat card."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(str(count), size=36, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(title, size=13, color="grey"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=config.SURFACE_COLOR,
            border_radius=12,
            padding=20,
            width=180,
            alignment=ft.alignment.center,
        )
    
    def _build_issues_list(self, issues: list, color: str, icon: str) -> ft.Column:
        """Build a list of issues."""
        items = []
        for issue in issues:
            items.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(icon, color=color, size=20),
                            ft.Text(issue, color="white", size=13, expand=True),
                        ],
                        spacing=10,
                    ),
                    bgcolor=config.SURFACE_COLOR,
                    border_radius=8,
                    padding=12,
                )
            )
        return ft.Column(items, spacing=8)
    
    def _load_gdpr(self):
        """Load GDPR data."""
        # Get export requests
        exports = api_client.get_gdpr_export_requests()
        erasures = api_client.get_gdpr_erasure_requests()
        
        # Summary stats
        pending_exports = len([e for e in exports if e.get("status") == "pending"]) if exports else 0
        pending_erasures = len([e for e in erasures if e.get("status") == "pending"]) if erasures else 0
        
        summary_row = ft.Row(
            [
                self._build_summary_card("Export Requests", len(exports) if exports else 0, config.PRIMARY_COLOR),
                self._build_summary_card("Pending Exports", pending_exports, config.WARNING_COLOR),
                self._build_summary_card("Erasure Requests", len(erasures) if erasures else 0, config.PRIMARY_COLOR),
                self._build_summary_card("Pending Erasures", pending_erasures, config.WARNING_COLOR),
            ],
            spacing=20,
            wrap=True,
        )
        
        # Recent requests tables
        exports_section = ft.Column(
            [
                ft.Text("Recent Data Export Requests", size=16, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                self._build_requests_table(exports, "export") if exports else
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.INBOX, size=48, color="grey"),
                            ft.Text("No export requests", color="grey"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=config.SURFACE_COLOR,
                    border_radius=8,
                    padding=30,
                    alignment=ft.alignment.center,
                ),
            ],
        )
        
        erasures_section = ft.Column(
            [
                ft.Text("Data Erasure Requests", size=16, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                self._build_requests_table(erasures, "erasure") if erasures else
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.INBOX, size=48, color="grey"),
                            ft.Text("No erasure requests", color="grey"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=config.SURFACE_COLOR,
                    border_radius=8,
                    padding=30,
                    alignment=ft.alignment.center,
                ),
            ],
        )
        
        self.gdpr_container.content = ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.PRIVACY_TIP, color=config.PRIMARY_COLOR, size=32),
                            ft.Column(
                                [
                                    ft.Text("GDPR Compliance Dashboard", size=18, weight=ft.FontWeight.BOLD, color="white"),
                                    ft.Text("Manage data subject requests across all tenants", color="grey"),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=15,
                    ),
                    bgcolor=config.SURFACE_COLOR,
                    border_radius=12,
                    padding=20,
                ),
                ft.Container(height=20),
                summary_row,
                ft.Container(height=30),
                exports_section,
                ft.Container(height=30),
                erasures_section,
            ],
            scroll=ft.ScrollMode.AUTO,
        )
        
        self.update()
    
    def _build_requests_table(self, requests: list, request_type: str) -> ft.Container:
        """Build a requests table."""
        if not requests:
            return ft.Container()
        
        rows = []
        for req in requests[:10]:  # Show last 10
            status = req.get("status", "unknown")
            status_color = {
                "pending": config.WARNING_COLOR,
                "completed": config.SUCCESS_COLOR,
                "failed": config.ERROR_COLOR,
            }.get(status, "grey")
            
            rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(req.get("customer_id", "Unknown")[:12] + "...", color="white", width=120),
                            ft.Text(req.get("created_at", "")[:10], color="grey", width=100),
                            StatusBadge(status, size="small"),
                            ft.Text(req.get("tenant_id", "")[:12] if req.get("tenant_id") else "-", color="grey", width=120),
                        ],
                        spacing=20,
                    ),
                    padding=ft.padding.symmetric(vertical=8, horizontal=15),
                    border=ft.border.only(bottom=ft.BorderSide(1, "#3d4043")),
                )
            )
        
        # Header
        header = ft.Container(
            content=ft.Row(
                [
                    ft.Text("Customer ID", weight=ft.FontWeight.BOLD, color="grey", width=120),
                    ft.Text("Date", weight=ft.FontWeight.BOLD, color="grey", width=100),
                    ft.Text("Status", weight=ft.FontWeight.BOLD, color="grey", width=80),
                    ft.Text("Tenant", weight=ft.FontWeight.BOLD, color="grey", width=120),
                ],
                spacing=20,
            ),
            padding=ft.padding.symmetric(vertical=10, horizontal=15),
            bgcolor="#252729",
            border_radius=ft.border_radius.only(top_left=8, top_right=8),
        )
        
        return ft.Container(
            content=ft.Column([header] + rows, spacing=0),
            border=ft.border.all(1, "#3d4043"),
            border_radius=8,
        )
