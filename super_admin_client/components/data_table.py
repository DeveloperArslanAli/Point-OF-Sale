"""Data table component with pagination and sorting."""
from dataclasses import dataclass
from typing import Callable, Any

import flet as ft

from config import config


@dataclass
class DataTableColumn:
    """Column definition for data table."""
    
    key: str
    label: str
    width: int | None = None
    sortable: bool = True
    render: Callable[[Any], ft.Control] | None = None


class DataTable(ft.Container):
    """Paginated data table with sorting and search."""
    
    def __init__(
        self,
        columns: list[DataTableColumn],
        data: list[dict],
        page_size: int = 10,
        total_items: int | None = None,
        current_page: int = 1,
        on_page_change: Callable[[int], None] | None = None,
        on_row_click: Callable[[dict], None] | None = None,
        on_sort: Callable[[str, bool], None] | None = None,
        show_search: bool = True,
        search_placeholder: str = "Search...",
        on_search: Callable[[str], None] | None = None,
        loading: bool = False,
        empty_message: str = "No data available",
    ):
        super().__init__()
        self.columns = columns
        self._data = data
        self.page_size = page_size
        self._total_items = total_items or len(data)
        self._current_page = current_page
        self.on_page_change = on_page_change
        self.on_row_click = on_row_click
        self.on_sort = on_sort
        self.show_search = show_search
        self.search_placeholder = search_placeholder
        self.on_search = on_search
        self._loading = loading
        self.empty_message = empty_message
        
        self._sort_column: str | None = None
        self._sort_ascending: bool = True
        
        self.expand = True
        self._build()
    
    def _build(self):
        """Build the data table."""
        # Search bar
        search_bar = None
        if self.show_search:
            self.search_field = ft.TextField(
                hint_text=self.search_placeholder,
                prefix_icon=ft.Icons.SEARCH,
                border_radius=8,
                height=40,
                text_size=14,
                on_change=self._on_search_change,
                expand=True,
            )
            search_bar = ft.Container(
                content=ft.Row([self.search_field]),
                margin=ft.margin.only(bottom=10),
            )
        
        # Table header
        header_cells = []
        for col in self.columns:
            header_content = ft.Row(
                [
                    ft.Text(col.label, weight=ft.FontWeight.BOLD, color="white", size=13),
                    ft.Icon(
                        ft.Icons.ARROW_UPWARD if self._sort_ascending else ft.Icons.ARROW_DOWNWARD,
                        size=14,
                        color=config.PRIMARY_COLOR,
                        visible=self._sort_column == col.key,
                    ) if col.sortable else ft.Container(),
                ],
                spacing=5,
            )
            
            header_cell = ft.Container(
                content=header_content,
                padding=ft.padding.symmetric(horizontal=10, vertical=12),
                bgcolor=config.SURFACE_COLOR,
                on_click=lambda e, c=col: self._on_header_click(c) if c.sortable else None,
                ink=col.sortable,
                width=col.width,
            )
            header_cells.append(header_cell)
        
        header_row = ft.Container(
            content=ft.Row(header_cells, spacing=0),
            bgcolor="#252729",
            border_radius=ft.border_radius.only(top_left=8, top_right=8),
        )
        
        # Table rows
        if self._loading:
            rows_content = ft.Container(
                content=ft.Column(
                    [
                        ft.ProgressRing(width=30, height=30, color=config.PRIMARY_COLOR),
                        ft.Text("Loading...", color="grey"),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                height=200,
                alignment=ft.alignment.center,
            )
        elif not self._data:
            rows_content = ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.INBOX, size=48, color="grey"),
                        ft.Text(self.empty_message, color="grey"),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                height=200,
                alignment=ft.alignment.center,
            )
        else:
            data_rows = []
            for idx, row_data in enumerate(self._data):
                cells = []
                for col in self.columns:
                    value = row_data.get(col.key, "")
                    
                    if col.render:
                        cell_content = col.render(row_data)
                    else:
                        cell_content = ft.Text(
                            str(value) if value is not None else "-",
                            size=13,
                            color="white",
                        )
                    
                    cell = ft.Container(
                        content=cell_content,
                        padding=ft.padding.symmetric(horizontal=10, vertical=10),
                        width=col.width,
                    )
                    cells.append(cell)
                
                row = ft.Container(
                    content=ft.Row(cells, spacing=0),
                    bgcolor=config.SURFACE_COLOR if idx % 2 == 0 else "#252729",
                    on_click=lambda e, d=row_data: self._on_row_click(d),
                    on_hover=self._on_row_hover,
                    ink=bool(self.on_row_click),
                )
                data_rows.append(row)
            
            rows_content = ft.Column(data_rows, spacing=0, scroll=ft.ScrollMode.AUTO)
        
        # Pagination
        total_pages = max(1, (self._total_items + self.page_size - 1) // self.page_size)
        
        pagination = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        f"Showing {min((self._current_page - 1) * self.page_size + 1, self._total_items)}-"
                        f"{min(self._current_page * self.page_size, self._total_items)} of {self._total_items}",
                        size=12,
                        color="grey",
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.CHEVRON_LEFT,
                        icon_color="white" if self._current_page > 1 else "grey",
                        disabled=self._current_page <= 1,
                        on_click=lambda e: self._change_page(self._current_page - 1),
                    ),
                    ft.Text(f"{self._current_page} / {total_pages}", color="white", size=13),
                    ft.IconButton(
                        icon=ft.Icons.CHEVRON_RIGHT,
                        icon_color="white" if self._current_page < total_pages else "grey",
                        disabled=self._current_page >= total_pages,
                        on_click=lambda e: self._change_page(self._current_page + 1),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            bgcolor="#252729",
            border_radius=ft.border_radius.only(bottom_left=8, bottom_right=8),
        )
        
        self.content = ft.Column(
            [
                search_bar if search_bar else ft.Container(),
                ft.Container(
                    content=ft.Column(
                        [header_row, rows_content, pagination],
                        spacing=0,
                    ),
                    border=ft.border.all(1, "#3d4043"),
                    border_radius=8,
                ),
            ],
            spacing=0,
        )
    
    def _on_search_change(self, e):
        """Handle search input change."""
        if self.on_search:
            self.on_search(e.control.value)
    
    def _on_header_click(self, column: DataTableColumn):
        """Handle column header click for sorting."""
        if self._sort_column == column.key:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column.key
            self._sort_ascending = True
        
        if self.on_sort:
            self.on_sort(column.key, self._sort_ascending)
        
        self._build()
        self.update()
    
    def _on_row_click(self, row_data: dict):
        """Handle row click."""
        if self.on_row_click:
            self.on_row_click(row_data)
    
    def _on_row_hover(self, e: ft.ControlEvent):
        """Handle row hover."""
        if e.data == "true":
            e.control.bgcolor = f"{config.PRIMARY_COLOR}10"
        else:
            # Reset to alternating colors
            e.control.bgcolor = config.SURFACE_COLOR
        e.control.update()
    
    def _change_page(self, page: int):
        """Change current page."""
        self._current_page = page
        if self.on_page_change:
            self.on_page_change(page)
        self._build()
        self.update()
    
    def set_data(self, data: list[dict], total_items: int | None = None):
        """Update table data."""
        self._data = data
        self._total_items = total_items or len(data)
        self._build()
        self.update()
    
    def set_loading(self, loading: bool):
        """Set loading state."""
        self._loading = loading
        self._build()
        self.update()
    
    def set_page(self, page: int):
        """Set current page."""
        self._current_page = page
        self._build()
        self.update()
