"""System Monitoring view."""
import flet as ft

from config import config
from services.api_v2 import api_client
from components.stat_card import StatCard
from components.badge import StatusBadge, HealthIndicator
from components.loading import LoadingIndicator


class MonitoringView(ft.Container):
    """System monitoring and health dashboard."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        
        self._build()
    
    def _build(self):
        """Build the monitoring view layout."""
        # Refresh button
        refresh_row = ft.Row(
            [
                ft.Text("Real-time system health and performance metrics", color="grey"),
                ft.Container(expand=True),
                ft.ElevatedButton(
                    "Refresh All",
                    icon=ft.Icons.REFRESH,
                    bgcolor=config.PRIMARY_COLOR,
                    color="white",
                    on_click=self._refresh_all,
                ),
            ],
        )
        
        # Health overview section
        self.health_section = self._build_health_section()
        
        # Celery workers section
        self.workers_section = self._build_workers_section()
        
        # Database section
        self.database_section = self._build_database_section()
        
        self.content = ft.Column(
            [
                refresh_row,
                ft.Container(height=20),
                
                # Stats row
                self._build_stats_row(),
                ft.Container(height=30),
                
                # Three-column layout
                ft.Row(
                    [
                        ft.Column([self.health_section], expand=True),
                        ft.Column([self.workers_section], expand=True),
                        ft.Column([self.database_section], expand=True),
                    ],
                    spacing=20,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
    
    def _build_stats_row(self):
        """Build the stats cards row."""
        self.api_status_card = StatCard(
            title="API Server",
            value="...",
            icon=ft.Icons.DNS,
            subtitle="Checking...",
        )
        
        self.db_status_card = StatCard(
            title="Database",
            value="...",
            icon=ft.Icons.STORAGE,
            subtitle="Checking...",
        )
        
        self.celery_status_card = StatCard(
            title="Celery Workers",
            value="...",
            icon=ft.Icons.MEMORY,
            subtitle="Checking...",
        )
        
        self.queues_card = StatCard(
            title="Task Queues",
            value="...",
            icon=ft.Icons.QUEUE,
            subtitle="Checking...",
        )
        
        return ft.Row(
            [
                self.api_status_card,
                self.db_status_card,
                self.celery_status_card,
                self.queues_card,
            ],
            wrap=True,
            spacing=15,
            run_spacing=15,
        )
    
    def _build_health_section(self):
        """Build the overall health section."""
        self.health_container = ft.Container(
            content=LoadingIndicator(message="Loading..."),
            bgcolor=config.SURFACE_COLOR,
            border_radius=12,
            padding=20,
            height=250,
        )
        
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.HEALTH_AND_SAFETY, color=config.PRIMARY_COLOR),
                        ft.Text("System Health", size=16, weight=ft.FontWeight.BOLD, color="white"),
                    ],
                    spacing=10,
                ),
                ft.Container(height=10),
                self.health_container,
            ],
        )
    
    def _build_workers_section(self):
        """Build the Celery workers section."""
        self.workers_container = ft.Container(
            content=LoadingIndicator(message="Loading..."),
            bgcolor=config.SURFACE_COLOR,
            border_radius=12,
            padding=20,
            height=250,
        )
        
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.PEOPLE_ALT, color=config.PRIMARY_COLOR),
                        ft.Text("Celery Workers", size=16, weight=ft.FontWeight.BOLD, color="white"),
                    ],
                    spacing=10,
                ),
                ft.Container(height=10),
                self.workers_container,
            ],
        )
    
    def _build_database_section(self):
        """Build the database health section."""
        self.database_container = ft.Container(
            content=LoadingIndicator(message="Loading..."),
            bgcolor=config.SURFACE_COLOR,
            border_radius=12,
            padding=20,
            height=250,
        )
        
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TABLE_CHART, color=config.PRIMARY_COLOR),
                        ft.Text("Database Stats", size=16, weight=ft.FontWeight.BOLD, color="white"),
                    ],
                    spacing=10,
                ),
                ft.Container(height=10),
                self.database_container,
            ],
        )
    
    def did_mount(self):
        """Load data on mount."""
        self._refresh_all(None)
    
    def _refresh_all(self, e):
        """Refresh all monitoring data."""
        self._load_health()
        self._load_workers()
        self._load_database()
    
    def _load_health(self):
        """Load overall health status."""
        # Get detailed health
        health = api_client.get_detailed_health()
        
        if health and not health.get("error"):
            status = health.get("status", "unknown")
            components = health.get("components", {})
            
            # Update API status card
            api_status = components.get("api", {}).get("status", "unknown")
            self.api_status_card.update_value("Online" if api_status == "healthy" else "Issues")
            self.api_status_card.subtitle = api_status.title()
            
            # Build health display
            health_items = []
            for comp_name, comp_data in components.items():
                comp_status = comp_data.get("status", "unknown") if isinstance(comp_data, dict) else "unknown"
                health_items.append(
                    HealthIndicator(
                        comp_name.title(),
                        comp_status,
                    )
                )
            
            # Overall status banner
            if status == "healthy":
                banner_color = config.SUCCESS_COLOR
                banner_icon = ft.Icons.CHECK_CIRCLE
                banner_text = "All Systems Operational"
            elif status == "degraded":
                banner_color = config.WARNING_COLOR
                banner_icon = ft.Icons.WARNING
                banner_text = "Degraded Performance"
            else:
                banner_color = config.ERROR_COLOR
                banner_icon = ft.Icons.ERROR
                banner_text = "System Issues Detected"
            
            self.health_container.content = ft.Column(
                [
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(banner_icon, color="white", size=24),
                                ft.Text(banner_text, color="white", weight=ft.FontWeight.BOLD),
                            ],
                            spacing=10,
                        ),
                        bgcolor=banner_color,
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=15, vertical=10),
                    ),
                    ft.Container(height=15),
                    ft.Column(health_items, spacing=10),
                ],
            )
        else:
            self.health_container.content = ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color="grey"),
                    ft.Text("Unable to load health status", color="grey"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        
        self.update()
    
    def _load_workers(self):
        """Load Celery workers status."""
        workers = api_client.get_celery_workers()
        queues = api_client.get_celery_queues()
        
        # Update stats cards
        worker_count = workers.get("count", 0) if workers else 0
        self.celery_status_card.update_value(str(worker_count))
        self.celery_status_card.subtitle = "active workers"
        
        queue_count = len(queues.get("queues", {})) if queues else 0
        self.queues_card.update_value(str(queue_count))
        self.queues_card.subtitle = "queues configured"
        
        if workers and not workers.get("error"):
            worker_list = workers.get("workers", [])
            
            if worker_list:
                worker_items = []
                for worker in worker_list:
                    name = worker.get("name", "Unknown")
                    active_tasks = worker.get("active_tasks", 0)
                    
                    worker_items.append(
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.TERMINAL, size=20, color=config.SUCCESS_COLOR),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                name.split("@")[-1] if "@" in name else name,
                                                weight=ft.FontWeight.W_500,
                                                color="white",
                                                size=13,
                                            ),
                                            ft.Text(
                                                f"{active_tasks} active tasks",
                                                size=11,
                                                color="grey",
                                            ),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                    StatusBadge("active", size="small"),
                                ],
                                spacing=10,
                            ),
                            padding=ft.padding.symmetric(vertical=8),
                            border=ft.border.only(bottom=ft.BorderSide(1, "#3d4043")),
                        )
                    )
                
                self.workers_container.content = ft.Column(
                    worker_items,
                    scroll=ft.ScrollMode.AUTO,
                )
            else:
                self.workers_container.content = ft.Column(
                    [
                        ft.Icon(ft.Icons.WARNING, size=48, color=config.WARNING_COLOR),
                        ft.Text("No active workers", color=config.WARNING_COLOR, weight=ft.FontWeight.BOLD),
                        ft.Text("Background tasks will not be processed", color="grey", size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                )
        else:
            self.workers_container.content = ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color="grey"),
                    ft.Text("Unable to load workers", color="grey"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        
        self.update()
    
    def _load_database(self):
        """Load database health and stats."""
        db_health = api_client.check_database_health()
        
        if db_health and not db_health.get("error"):
            status = db_health.get("status", "unknown")
            connected = db_health.get("connected", False)
            table_counts = db_health.get("table_counts", {})
            
            # Update card
            self.db_status_card.update_value("Connected" if connected else "Disconnected")
            self.db_status_card.subtitle = status.title()
            
            # Build stats display
            stat_rows = []
            for table, count in table_counts.items():
                stat_rows.append(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.TABLE_ROWS, size=18, color="grey"),
                            ft.Text(table.title(), color="white", size=13, expand=True),
                            ft.Text(f"{count:,}", color=config.PRIMARY_COLOR, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=10,
                    )
                )
            
            status_color = config.SUCCESS_COLOR if connected else config.ERROR_COLOR
            
            self.database_container.content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE if connected else ft.Icons.ERROR,
                                color=status_color,
                                size=24,
                            ),
                            ft.Text(
                                "Connected" if connected else "Disconnected",
                                color=status_color,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Divider(color="#3d4043"),
                    ft.Text("Table Counts", weight=ft.FontWeight.BOLD, color="white", size=13),
                    ft.Container(height=5),
                    ft.Column(stat_rows, spacing=8),
                    ft.Container(expand=True),
                    ft.Text(
                        f"Last checked: {db_health.get('checked_at', 'Unknown')[:19]}",
                        size=10,
                        color="grey",
                    ),
                ],
            )
        else:
            self.db_status_card.update_value("Error")
            self.database_container.content = ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=config.ERROR_COLOR),
                    ft.Text("Database connection failed", color=config.ERROR_COLOR),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        
        self.update()
