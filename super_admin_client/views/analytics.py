"""Analytics view for system-wide metrics and insights."""
import flet as ft
from datetime import datetime

from config import config
from services.api_v2 import api_client
from components.stat_card import StatCard
from components.loading import LoadingIndicator


class AnalyticsView(ft.Container):
    """System-wide analytics dashboard."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        
        # Date range state
        self.date_range = "last_30_days"
        
        self._build()
    
    def _build(self):
        """Build the analytics view."""
        # Date range selector
        self.date_dropdown = ft.Dropdown(
            value="last_30_days",
            options=[
                ft.dropdown.Option("today", "Today"),
                ft.dropdown.Option("last_7_days", "Last 7 Days"),
                ft.dropdown.Option("last_30_days", "Last 30 Days"),
                ft.dropdown.Option("last_90_days", "Last 90 Days"),
                ft.dropdown.Option("this_year", "This Year"),
            ],
            width=200,
            on_change=self._on_date_change,
        )
        
        # Summary stats row
        self.stats_row = ft.Row([], wrap=True, spacing=20)
        
        # Revenue section
        self.revenue_section = ft.Container(
            content=LoadingIndicator(message="Loading revenue data..."),
            expand=True,
        )
        
        # Tenant activity section
        self.activity_section = ft.Container(
            content=LoadingIndicator(message="Loading activity..."),
            expand=True,
        )
        
        # Top tenants section
        self.top_tenants_section = ft.Container(
            content=LoadingIndicator(message="Loading tenant rankings..."),
            expand=True,
        )
        
        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("System Analytics Overview", color="grey"),
                        ft.Container(expand=True),
                        self.date_dropdown,
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            tooltip="Refresh",
                            on_click=lambda e: self._load_data(),
                        ),
                    ],
                ),
                ft.Container(height=20),
                self.stats_row,
                ft.Container(height=30),
                ft.Row(
                    [
                        ft.Container(
                            content=self.revenue_section,
                            expand=1,
                        ),
                        ft.Container(
                            content=self.top_tenants_section,
                            expand=1,
                        ),
                    ],
                    spacing=20,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                ft.Container(height=30),
                self.activity_section,
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
    
    def _on_date_change(self, e):
        """Handle date range change."""
        self.date_range = e.control.value
        self._load_data()
    
    def did_mount(self):
        """Load data on mount."""
        self._load_data()
    
    def _load_data(self):
        """Load all analytics data."""
        self._load_stats()
        self._load_revenue()
        self._load_activity()
        self._load_top_tenants()
    
    def _load_stats(self):
        """Load summary statistics."""
        stats = api_client.get_stats()
        
        if stats and not stats.get("error"):
            cards = [
                StatCard(
                    title="Total Revenue",
                    value=f"${stats.get('total_revenue', 0):,.2f}",
                    icon=ft.Icons.ATTACH_MONEY,
                    color=config.SUCCESS_COLOR,
                    subtitle="System-wide revenue",
                ),
                StatCard(
                    title="Active Tenants",
                    value=str(stats.get("active_tenants", 0)),
                    icon=ft.Icons.BUSINESS,
                    color=config.PRIMARY_COLOR,
                    subtitle="Currently active",
                ),
                StatCard(
                    title="Total Users",
                    value=str(stats.get("total_users", 0)),
                    icon=ft.Icons.PEOPLE,
                    color="#9c27b0",
                    subtitle="All platform users",
                ),
                StatCard(
                    title="Total Transactions",
                    value=str(stats.get("total_transactions", 0)),
                    icon=ft.Icons.RECEIPT_LONG,
                    color="#ff5722",
                    subtitle="Processed transactions",
                ),
            ]
            self.stats_row.controls = cards
        else:
            # Show placeholder stats
            self.stats_row.controls = [
                StatCard("Total Revenue", "$--.--", ft.Icons.ATTACH_MONEY, config.SUCCESS_COLOR),
                StatCard("Active Tenants", "--", ft.Icons.BUSINESS, config.PRIMARY_COLOR),
                StatCard("Total Users", "--", ft.Icons.PEOPLE, "#9c27b0"),
                StatCard("Transactions", "--", ft.Icons.RECEIPT_LONG, "#ff5722"),
            ]
        
        self.update()
    
    def _load_revenue(self):
        """Load revenue breakdown."""
        # Get billing analytics
        billing = api_client.get_billing_analytics()
        
        if billing and not billing.get("error"):
            mrr = billing.get("mrr", 0)
            arr = billing.get("arr", 0)
            churn_rate = billing.get("churn_rate", 0)
            growth_rate = billing.get("growth_rate", 0)
            
            self.revenue_section.content = ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Revenue Metrics", size=18, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Divider(height=20, color=config.BORDER_COLOR),
                        
                        # MRR & ARR row
                        ft.Row(
                            [
                                self._build_metric_box("MRR", f"${mrr:,.2f}", config.SUCCESS_COLOR),
                                self._build_metric_box("ARR", f"${arr:,.2f}", config.PRIMARY_COLOR),
                            ],
                            spacing=15,
                        ),
                        ft.Container(height=15),
                        
                        # Growth & Churn row
                        ft.Row(
                            [
                                self._build_metric_box(
                                    "Growth Rate",
                                    f"{growth_rate:.1f}%",
                                    config.SUCCESS_COLOR if growth_rate > 0 else config.ERROR_COLOR,
                                    icon=ft.Icons.TRENDING_UP if growth_rate > 0 else ft.Icons.TRENDING_DOWN,
                                ),
                                self._build_metric_box(
                                    "Churn Rate",
                                    f"{churn_rate:.1f}%",
                                    config.ERROR_COLOR if churn_rate > 5 else config.SUCCESS_COLOR,
                                    icon=ft.Icons.PERSON_REMOVE,
                                ),
                            ],
                            spacing=15,
                        ),
                        ft.Container(height=20),
                        
                        # Revenue by plan
                        ft.Text("Revenue by Plan", size=14, weight=ft.FontWeight.W_500, color="white"),
                        ft.Container(height=10),
                        self._build_revenue_breakdown(billing.get("by_plan", {})),
                    ],
                ),
                bgcolor=config.SURFACE_COLOR,
                border_radius=12,
                padding=20,
            )
        else:
            self.revenue_section.content = self._build_empty_section(
                "Revenue Analytics",
                "Revenue data not available",
            )
        
        self.update()
    
    def _build_metric_box(self, label: str, value: str, color: str, icon=None) -> ft.Container:
        """Build a small metric display box."""
        content_row = [
            ft.Text(value, size=24, weight=ft.FontWeight.BOLD, color=color),
        ]
        if icon:
            content_row.append(ft.Icon(icon, color=color, size=18))
        
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(content_row, spacing=5),
                    ft.Text(label, size=12, color="grey"),
                ],
                spacing=2,
            ),
            bgcolor="#252729",
            border_radius=8,
            padding=15,
            expand=True,
        )
    
    def _build_revenue_breakdown(self, by_plan: dict) -> ft.Column:
        """Build revenue by plan breakdown."""
        if not by_plan:
            return ft.Column([ft.Text("No plan breakdown available", color="grey")])
        
        total = sum(by_plan.values())
        rows = []
        
        for plan_name, amount in sorted(by_plan.items(), key=lambda x: x[1], reverse=True):
            pct = (amount / total * 100) if total > 0 else 0
            
            rows.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(plan_name, color="white", size=13),
                                ft.Container(expand=True),
                                ft.Text(f"${amount:,.2f}", color="white", weight=ft.FontWeight.W_500),
                            ],
                        ),
                        ft.ProgressBar(
                            value=pct / 100,
                            bgcolor="#3d4043",
                            color=config.PRIMARY_COLOR,
                            height=6,
                        ),
                    ],
                    spacing=5,
                )
            )
        
        return ft.Column(rows, spacing=10)
    
    def _load_activity(self):
        """Load tenant activity metrics."""
        # Get activity data - this could come from various endpoints
        signups = api_client.get_recent_signups()
        
        if signups and isinstance(signups, list):
            # Build recent signups list
            signup_items = []
            for signup in signups[:7]:  # Show last 7
                tenant_name = signup.get("company_name") or signup.get("name", "Unknown")
                created_at = signup.get("created_at", "")
                plan = signup.get("subscription_plan", "Free")
                
                signup_items.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.CircleAvatar(
                                    content=ft.Text(tenant_name[0].upper() if tenant_name else "?"),
                                    bgcolor=config.PRIMARY_COLOR,
                                    radius=18,
                                ),
                                ft.Column(
                                    [
                                        ft.Text(tenant_name, color="white", size=14),
                                        ft.Text(created_at[:10] if created_at else "-", color="grey", size=11),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Container(
                                    content=ft.Text(plan, size=11, color="white"),
                                    bgcolor=config.PRIMARY_COLOR,
                                    border_radius=4,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                ),
                            ],
                            spacing=12,
                        ),
                        padding=ft.padding.symmetric(vertical=8),
                        border=ft.border.only(bottom=ft.BorderSide(1, "#3d4043")),
                    )
                )
            
            self.activity_section.content = ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("Recent Tenant Signups", size=18, weight=ft.FontWeight.BOLD, color="white"),
                                ft.Container(expand=True),
                                ft.TextButton(
                                    "View All",
                                    on_click=lambda e: self.app.navigate("tenants"),
                                ),
                            ],
                        ),
                        ft.Divider(height=15, color=config.BORDER_COLOR),
                        ft.Column(signup_items) if signup_items else 
                        ft.Text("No recent signups", color="grey"),
                    ],
                ),
                bgcolor=config.SURFACE_COLOR,
                border_radius=12,
                padding=20,
            )
        else:
            self.activity_section.content = self._build_empty_section(
                "Recent Activity",
                "Activity data not available",
            )
        
        self.update()
    
    def _load_top_tenants(self):
        """Load top performing tenants."""
        # Get tenants with user counts to rank them
        tenants = api_client.get_tenants(page=1, size=10)
        
        if tenants and not tenants.get("error"):
            items = tenants.get("items", [])
            
            # Sort by user count
            sorted_tenants = sorted(items, key=lambda x: x.get("user_count", 0), reverse=True)[:5]
            
            ranking_items = []
            for i, tenant in enumerate(sorted_tenants, 1):
                name = tenant.get("company_name") or tenant.get("name", "Unknown")
                user_count = tenant.get("user_count", 0)
                
                # Rank badge color
                rank_colors = {1: "#ffd700", 2: "#c0c0c0", 3: "#cd7f32"}
                rank_color = rank_colors.get(i, "grey")
                
                ranking_items.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(
                                    content=ft.Text(f"#{i}", color="white", weight=ft.FontWeight.BOLD),
                                    bgcolor=rank_color if i <= 3 else "#3d4043",
                                    width=32,
                                    height=32,
                                    border_radius=16,
                                    alignment=ft.alignment.center,
                                ),
                                ft.Column(
                                    [
                                        ft.Text(name, color="white", size=14),
                                        ft.Text(f"{user_count} users", color="grey", size=11),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                            ],
                            spacing=12,
                        ),
                        padding=ft.padding.symmetric(vertical=8),
                        border=ft.border.only(bottom=ft.BorderSide(1, "#3d4043")) if i < len(sorted_tenants) else None,
                    )
                )
            
            self.top_tenants_section.content = ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Top Tenants by Users", size=18, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Divider(height=15, color=config.BORDER_COLOR),
                        ft.Column(ranking_items) if ranking_items else
                        ft.Text("No tenant data available", color="grey"),
                    ],
                ),
                bgcolor=config.SURFACE_COLOR,
                border_radius=12,
                padding=20,
            )
        else:
            self.top_tenants_section.content = self._build_empty_section(
                "Top Tenants",
                "Tenant ranking not available",
            )
        
        self.update()
    
    def _build_empty_section(self, title: str, message: str) -> ft.Container:
        """Build an empty state section."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Divider(height=15, color=config.BORDER_COLOR),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.ANALYTICS, size=48, color="grey"),
                                ft.Text(message, color="grey"),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                        padding=40,
                        alignment=ft.alignment.center,
                    ),
                ],
            ),
            bgcolor=config.SURFACE_COLOR,
            border_radius=12,
            padding=20,
        )
