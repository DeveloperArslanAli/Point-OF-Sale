"""Dashboard view for Super Admin Portal.

Displays system-wide statistics, health status, and quick actions.
"""
import flet as ft

from config import config
from services.api_v2 import api_client
from components.stat_card import StatCard
from components.badge import StatusBadge, HealthIndicator
from components.loading import LoadingIndicator


class DashboardView(ft.Container):
    """Main dashboard with system overview."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        
        self._build()
    
    def _build(self):
        """Build the dashboard layout."""
        self.content = ft.Column(
            [
                # Refresh button row
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            icon_color="white",
                            tooltip="Refresh Data",
                            on_click=self._refresh_data,
                        ),
                    ],
                ),
                
                # Stats cards section
                ft.Text("System Overview", size=18, weight=ft.FontWeight.BOLD, color="white"),
                ft.Container(height=10),
                self._build_stats_section(),
                ft.Container(height=30),
                
                # Two-column layout
                ft.Row(
                    [
                        # Left column - Health & Compliance
                        ft.Column(
                            [
                                self._build_health_section(),
                                ft.Container(height=20),
                                self._build_compliance_section(),
                            ],
                            expand=True,
                        ),
                        
                        # Right column - Recent activity
                        ft.Column(
                            [
                                self._build_recent_tenants_section(),
                            ],
                            expand=True,
                        ),
                    ],
                    spacing=20,
                    expand=True,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        )
    
    def _build_stats_section(self):
        """Build the stats cards row."""
        # Stat cards (values will be updated on mount)
        self.tenants_card = StatCard(
            title="Total Tenants",
            value="...",
            icon=ft.Icons.BUSINESS,
            subtitle="Loading...",
            on_click=lambda e: self.app._navigate("tenants"),
        )
        
        self.active_tenants_card = StatCard(
            title="Active Tenants",
            value="...",
            icon=ft.Icons.CHECK_CIRCLE,
            icon_color=config.SUCCESS_COLOR,
        )
        
        self.users_card = StatCard(
            title="Total Users",
            value="...",
            icon=ft.Icons.PEOPLE,
            subtitle="Across all tenants",
        )
        
        self.revenue_card = StatCard(
            title="Total Revenue",
            value="...",
            icon=ft.Icons.ATTACH_MONEY,
            icon_color=config.SUCCESS_COLOR,
            subtitle="All-time",
        )
        
        self.sales_card = StatCard(
            title="Total Sales",
            value="...",
            icon=ft.Icons.RECEIPT,
            subtitle="All-time transactions",
        )
        
        return ft.Row(
            [
                self.tenants_card,
                self.active_tenants_card,
                self.users_card,
                self.revenue_card,
                self.sales_card,
            ],
            wrap=True,
            spacing=15,
            run_spacing=15,
        )
    
    def _build_health_section(self):
        """Build the system health section."""
        self.health_container = ft.Container(
            content=LoadingIndicator(message="Loading health status..."),
            bgcolor=config.SURFACE_COLOR,
            border_radius=12,
            padding=20,
            height=200,
        )
        
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.MONITOR_HEART, color=config.PRIMARY_COLOR),
                        ft.Text("System Health", size=16, weight=ft.FontWeight.BOLD, color="white"),
                    ],
                    spacing=10,
                ),
                ft.Container(height=10),
                self.health_container,
            ],
        )
    
    def _build_compliance_section(self):
        """Build the compliance status section."""
        self.compliance_container = ft.Container(
            content=LoadingIndicator(message="Loading compliance..."),
            bgcolor=config.SURFACE_COLOR,
            border_radius=12,
            padding=20,
            height=180,
        )
        
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.SECURITY, color=config.PRIMARY_COLOR),
                        ft.Text("PCI Compliance", size=16, weight=ft.FontWeight.BOLD, color="white"),
                    ],
                    spacing=10,
                ),
                ft.Container(height=10),
                self.compliance_container,
            ],
        )
    
    def _build_recent_tenants_section(self):
        """Build the recent tenants section."""
        self.recent_tenants_container = ft.Container(
            content=LoadingIndicator(message="Loading tenants..."),
            bgcolor=config.SURFACE_COLOR,
            border_radius=12,
            padding=20,
            expand=True,
        )
        
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.BUSINESS, color=config.PRIMARY_COLOR),
                        ft.Text("Recent Tenants", size=16, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Container(expand=True),
                        ft.TextButton(
                            "View All",
                            on_click=lambda e: self.app._navigate("tenants"),
                        ),
                    ],
                    spacing=10,
                ),
                ft.Container(height=10),
                self.recent_tenants_container,
            ],
            expand=True,
        )
    
    def did_mount(self):
        """Load data when view is mounted."""
        self._refresh_data(None)
    
    def _refresh_data(self, e):
        """Refresh all dashboard data."""
        self._load_stats()
        self._load_health()
        self._load_compliance()
        self._load_recent_tenants()
    
    def _load_stats(self):
        """Load system statistics."""
        stats = api_client.get_system_stats()
        
        if stats and not stats.get("error"):
            self.tenants_card.update_value(str(stats.get("total_tenants", 0)))
            self.tenants_card.subtitle = f"{stats.get('active_tenants', 0)} active"
            
            self.active_tenants_card.update_value(str(stats.get("active_tenants", 0)))
            
            self.users_card.update_value(str(stats.get("total_users", 0)))
            self.users_card.subtitle = f"{stats.get('active_users', 0)} active"
            
            revenue = stats.get("total_revenue_all_time", 0)
            self.revenue_card.update_value(f"${revenue:,.2f}")
            
            self.sales_card.update_value(f"{stats.get('total_sales_all_time', 0):,}")
            
            self.update()
        else:
            self.tenants_card.update_value("Error")
    
    def _load_health(self):
        """Load system health status."""
        # Database health
        db_health = api_client.check_database_health()
        
        # Celery health
        celery_health = api_client.get_celery_workers()
        
        # Build health display
        db_status = db_health.get("status", "unknown") if db_health else "error"
        celery_status = "healthy" if celery_health.get("count", 0) > 0 else "no_workers"
        
        # Determine overall status
        if db_status == "healthy" and celery_status == "healthy":
            overall_status = "healthy"
            overall_color = config.SUCCESS_COLOR
        elif db_status == "unhealthy" or celery_status == "error":
            overall_status = "unhealthy"
            overall_color = config.ERROR_COLOR
        else:
            overall_status = "degraded"
            overall_color = config.WARNING_COLOR
        
        self.health_container.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Overall Status:", color="grey"),
                        StatusBadge(overall_status),
                    ],
                    spacing=10,
                ),
                ft.Divider(color="#3d4043"),
                HealthIndicator(
                    "Database",
                    db_status,
                    f"{db_health.get('table_counts', {}).get('tenants', '?')} tenants" if db_health else None,
                ),
                HealthIndicator(
                    "Celery Workers",
                    "healthy" if celery_health.get("count", 0) > 0 else "no_workers",
                    f"{celery_health.get('count', 0)} active" if celery_health else None,
                ),
                HealthIndicator(
                    "API Server",
                    "healthy",
                    "Running",
                ),
            ],
            spacing=10,
        )
        self.update()
    
    def _load_compliance(self):
        """Load PCI compliance status."""
        compliance = api_client.get_pci_compliance()
        
        if compliance and not compliance.get("error"):
            is_compliant = compliance.get("is_compliant", False)
            critical_count = len(compliance.get("critical_issues", []))
            warning_count = len(compliance.get("warnings", []))
            passed_count = len(compliance.get("passed_checks", []))
            
            status_text = "Compliant" if is_compliant else "Non-Compliant"
            status_color = config.SUCCESS_COLOR if is_compliant else config.ERROR_COLOR
            
            self.compliance_container.content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE if is_compliant else ft.Icons.WARNING,
                                color=status_color,
                                size=32,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        status_text,
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color=status_color,
                                    ),
                                    ft.Text(
                                        f"Last checked: {compliance.get('checked_at', 'Unknown')[:10]}",
                                        size=11,
                                        color="grey",
                                    ),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=15,
                    ),
                    ft.Divider(color="#3d4043"),
                    ft.Row(
                        [
                            self._build_compliance_stat("Critical", critical_count, config.ERROR_COLOR),
                            self._build_compliance_stat("Warnings", warning_count, config.WARNING_COLOR),
                            self._build_compliance_stat("Passed", passed_count, config.SUCCESS_COLOR),
                        ],
                        spacing=20,
                    ),
                ],
                spacing=15,
            )
        else:
            self.compliance_container.content = ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color="grey", size=32),
                    ft.Text("Unable to load compliance data", color="grey"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        
        self.update()
    
    def _build_compliance_stat(self, label: str, count: int, color: str) -> ft.Container:
        """Build a compliance stat display."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(str(count), size=24, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(label, size=11, color="grey"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            expand=True,
            alignment=ft.alignment.center,
        )
    
    def _load_recent_tenants(self):
        """Load recent tenants list."""
        result = api_client.get_all_tenants(page=1, page_size=5)
        
        if result and not result.get("error"):
            tenants = result.get("items", [])
            
            if tenants:
                tenant_rows = []
                for tenant in tenants:
                    is_active = tenant.get("is_active", False)
                    
                    row = ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(
                                    content=ft.Icon(ft.Icons.BUSINESS, size=20, color="grey"),
                                    width=40,
                                    height=40,
                                    border_radius=8,
                                    bgcolor="#3d4043",
                                    alignment=ft.alignment.center,
                                ),
                                ft.Column(
                                    [
                                        ft.Text(
                                            tenant.get("name", "Unknown"),
                                            weight=ft.FontWeight.W_500,
                                            color="white",
                                        ),
                                        ft.Text(
                                            tenant.get("slug", ""),
                                            size=11,
                                            color="grey",
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                StatusBadge(
                                    "active" if is_active else "suspended",
                                    size="small",
                                ),
                                ft.Text(
                                    f"{tenant.get('user_count', 0)} users",
                                    size=11,
                                    color="grey",
                                ),
                            ],
                            spacing=15,
                        ),
                        padding=ft.padding.symmetric(vertical=8),
                        border=ft.border.only(bottom=ft.BorderSide(1, "#3d4043")),
                    )
                    tenant_rows.append(row)
                
                self.recent_tenants_container.content = ft.Column(
                    tenant_rows,
                    spacing=0,
                    scroll=ft.ScrollMode.AUTO,
                )
            else:
                self.recent_tenants_container.content = ft.Column(
                    [
                        ft.Icon(ft.Icons.BUSINESS, size=48, color="grey"),
                        ft.Text("No tenants yet", color="grey"),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                )
        else:
            self.recent_tenants_container.content = ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color="grey", size=32),
                    ft.Text("Unable to load tenants", color="grey"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        
        self.update()
