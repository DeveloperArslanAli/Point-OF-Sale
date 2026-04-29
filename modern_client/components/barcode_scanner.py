"""Barcode Scanner Component for POS.

Provides barcode scanning functionality via:
1. USB/Keyboard barcode scanners (emulate keyboard input)
2. Camera-based scanning with pyzbar (optional, requires pyzbar + opencv-python)

USB Barcode Scanner Usage:
- Most USB scanners act as keyboard input devices
- They rapidly type the barcode followed by Enter
- This component detects rapid input patterns

Camera Scanner Usage:
- Requires: pyzbar, opencv-python
- Opens camera feed and scans for barcodes
- Falls back gracefully if dependencies unavailable
"""

import flet as ft
from datetime import datetime
from typing import Callable, Optional
import threading
import time

icons = ft.icons

# Try to import camera scanning dependencies
CAMERA_SCANNING_AVAILABLE = False
try:
    import cv2
    from pyzbar import pyzbar
    CAMERA_SCANNING_AVAILABLE = True
except ImportError:
    cv2 = None
    pyzbar = None


class BarcodeScanner:
    """USB Barcode Scanner handler using keyboard input detection.
    
    USB barcode scanners typically work by emulating keyboard input,
    rapidly typing the barcode number followed by Enter key.
    
    This class detects such rapid input patterns to distinguish
    barcode scans from regular typing.
    """
    
    def __init__(
        self,
        on_barcode_scanned: Callable[[str], None],
        min_length: int = 5,
        max_input_gap_ms: int = 50,
    ):
        """Initialize barcode scanner.
        
        Args:
            on_barcode_scanned: Callback when barcode is detected
            min_length: Minimum barcode length to accept
            max_input_gap_ms: Max milliseconds between keystrokes for barcode
        """
        self.on_barcode_scanned = on_barcode_scanned
        self.min_length = min_length
        self.max_input_gap_ms = max_input_gap_ms
        
        self._buffer = ""
        self._last_input_time: Optional[datetime] = None
        self._lock = threading.Lock()
    
    def handle_key_input(self, key: str) -> bool:
        """Process keyboard input for barcode detection.
        
        Args:
            key: Single character or special key name
            
        Returns:
            True if input was consumed as barcode, False otherwise
        """
        now = datetime.now()
        
        with self._lock:
            # Check if this is rapid input (barcode scanner)
            if self._last_input_time:
                gap_ms = (now - self._last_input_time).total_seconds() * 1000
                if gap_ms > self.max_input_gap_ms:
                    # Too slow - reset buffer (user typing)
                    self._buffer = ""
            
            self._last_input_time = now
            
            if key == "Enter":
                # Submit barcode if buffer is valid
                if len(self._buffer) >= self.min_length:
                    barcode = self._buffer
                    self._buffer = ""
                    self.on_barcode_scanned(barcode)
                    return True
                else:
                    self._buffer = ""
                    return False
            elif len(key) == 1 and (key.isdigit() or key.isalpha() or key == "-"):
                # Accumulate valid barcode characters
                self._buffer += key
                return True
            else:
                # Invalid character - reset
                self._buffer = ""
                return False
    
    def clear_buffer(self):
        """Clear the input buffer."""
        with self._lock:
            self._buffer = ""


class BarcodeScannerInput(ft.UserControl):
    """Flet barcode input component.
    
    Provides a text field that handles both manual entry and
    automatic USB barcode scanner detection.
    """
    
    def __init__(
        self,
        on_scan: Callable[[str], None],
        hint_text: str = "Scan barcode or enter SKU...",
        width: Optional[int] = None,
    ):
        super().__init__()
        self.on_scan = on_scan
        self.hint_text = hint_text
        self._width = width
        
        # Barcode detection
        self._scanner = BarcodeScanner(
            on_barcode_scanned=self._handle_barcode,
            min_length=5,
            max_input_gap_ms=100,
        )
        self._last_submit_time: Optional[datetime] = None
        
        # UI Components
        self._text_field: Optional[ft.TextField] = None
    
    def build(self):
        self._text_field = ft.TextField(
            hint_text=self.hint_text,
            prefix_icon=icons.QR_CODE_SCANNER,
            bgcolor="#2d3033",
            border_radius=10,
            border_width=0,
            color="white",
            width=self._width,
            expand=self._width is None,
            on_submit=self._on_manual_submit,
            autofocus=True,
        )
        
        return ft.Container(
            content=ft.Row(
                [
                    self._text_field,
                    ft.IconButton(
                        icon=icons.SEARCH,
                        icon_color="#bb86fc",
                        tooltip="Search",
                        on_click=self._on_search_click,
                    ),
                    ft.IconButton(
                        icon=icons.CAMERA_ALT,
                        icon_color="#bb86fc" if CAMERA_SCANNING_AVAILABLE else "grey",
                        tooltip="Camera Scan" if CAMERA_SCANNING_AVAILABLE else "Camera scanning unavailable",
                        on_click=self._open_camera_scanner if CAMERA_SCANNING_AVAILABLE else None,
                        disabled=not CAMERA_SCANNING_AVAILABLE,
                    ),
                ],
                spacing=5,
            ),
        )
    
    def _handle_barcode(self, barcode: str):
        """Handle detected barcode from USB scanner."""
        # Clear the text field and trigger callback
        if self._text_field:
            self._text_field.value = ""
            self._text_field.update()
        self.on_scan(barcode)
    
    def _on_manual_submit(self, e):
        """Handle manual text entry submission."""
        value = e.control.value.strip()
        if value:
            e.control.value = ""
            e.control.update()
            self.on_scan(value)
    
    def _on_search_click(self, e):
        """Handle search button click."""
        if self._text_field and self._text_field.value:
            value = self._text_field.value.strip()
            self._text_field.value = ""
            self._text_field.update()
            self.on_scan(value)
    
    def _open_camera_scanner(self, e):
        """Open camera scanner dialog."""
        if not CAMERA_SCANNING_AVAILABLE:
            return
        
        dialog = CameraScannerDialog(
            on_scan=self._handle_camera_scan,
        )
        
        if self.page:
            self.page.dialog = dialog
            dialog.open = True
            self.page.update()
    
    def _handle_camera_scan(self, barcode: str):
        """Handle barcode from camera scanner."""
        if self.page and self.page.dialog:
            self.page.dialog.open = False
            self.page.update()
        
        self.on_scan(barcode)
    
    def focus(self):
        """Focus the text field."""
        if self._text_field:
            self._text_field.focus()


class CameraScannerDialog(ft.AlertDialog):
    """Camera-based barcode scanner dialog.
    
    Opens camera and scans for barcodes using pyzbar.
    Requires: pyzbar, opencv-python
    """
    
    def __init__(
        self,
        on_scan: Callable[[str], None],
    ):
        self.on_scan = on_scan
        self._scanning = False
        self._camera_thread: Optional[threading.Thread] = None
        
        super().__init__(
            modal=True,
            title=ft.Text("Camera Scanner", color="white"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(icons.CAMERA_ALT, size=80, color="#bb86fc"),
                        ft.Text(
                            "Position barcode in front of camera",
                            color="white",
                            size=16,
                        ),
                        ft.ProgressRing(color="#bb86fc"),
                        ft.Text(
                            "Scanning...",
                            color="grey",
                            size=14,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=20,
                ),
                width=400,
                height=300,
                alignment=ft.alignment.center,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self._cancel_scan),
            ],
            on_dismiss=self._on_dismiss,
        )
    
    def did_mount(self):
        """Start camera scanning when dialog opens."""
        self._start_scanning()
    
    def _start_scanning(self):
        """Start the camera scanning thread."""
        if not CAMERA_SCANNING_AVAILABLE or self._scanning:
            return
        
        self._scanning = True
        self._camera_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._camera_thread.start()
    
    def _scan_loop(self):
        """Camera scanning loop (runs in background thread)."""
        if not CAMERA_SCANNING_AVAILABLE:
            return
        
        cap = None
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return
            
            while self._scanning:
                ret, frame = cap.read()
                if not ret:
                    continue
                
                # Decode barcodes
                barcodes = pyzbar.decode(frame)
                
                for barcode in barcodes:
                    barcode_data = barcode.data.decode("utf-8")
                    if barcode_data:
                        self._scanning = False
                        # Call callback on main thread
                        self.on_scan(barcode_data)
                        break
                
                time.sleep(0.05)  # ~20 FPS
                
        except Exception as e:
            print(f"Camera scan error: {e}")
        finally:
            if cap:
                cap.release()
    
    def _cancel_scan(self, e):
        """Cancel camera scanning."""
        self._scanning = False
        self.open = False
        if self.page:
            self.page.update()
    
    def _on_dismiss(self, e):
        """Handle dialog dismiss."""
        self._scanning = False


# Utility functions for product lookup

def lookup_product_by_barcode(
    barcode: str,
    products: list[dict],
) -> Optional[dict]:
    """Look up product by barcode/SKU.
    
    Args:
        barcode: Scanned barcode or SKU
        products: List of product dicts
        
    Returns:
        Matching product dict or None
    """
    barcode_lower = barcode.lower().strip()
    
    for product in products:
        # Check SKU
        sku = product.get("sku", "").lower()
        if sku == barcode_lower:
            return product
        
        # Check barcode field if exists
        product_barcode = product.get("barcode", "").lower()
        if product_barcode and product_barcode == barcode_lower:
            return product
        
        # Check UPC field if exists
        upc = product.get("upc", "").lower()
        if upc and upc == barcode_lower:
            return product
    
    return None


def format_barcode_display(barcode: str) -> str:
    """Format barcode for display.
    
    Args:
        barcode: Raw barcode string
        
    Returns:
        Formatted barcode (e.g., with hyphens for EAN-13)
    """
    # Remove any whitespace
    barcode = barcode.strip()
    
    # Format EAN-13 (13 digits)
    if len(barcode) == 13 and barcode.isdigit():
        return f"{barcode[0]}-{barcode[1:7]}-{barcode[7:12]}-{barcode[12]}"
    
    # Format UPC-A (12 digits)
    if len(barcode) == 12 and barcode.isdigit():
        return f"{barcode[0]}-{barcode[1:6]}-{barcode[6:11]}-{barcode[11]}"
    
    # Format EAN-8 (8 digits)
    if len(barcode) == 8 and barcode.isdigit():
        return f"{barcode[:4]}-{barcode[4:]}"
    
    return barcode
