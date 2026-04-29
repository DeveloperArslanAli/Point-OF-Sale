"""Configuration settings for Super Admin Portal."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
    APP_TITLE: str = "Retail POS - SuperAdmin Portal"
    APP_PORT: int = int(os.getenv("PORT", "8081"))
    
    # Token storage file
    AUTH_TOKEN_FILE: str = ".super_admin_tokens.json"
    
    # UI Theme
    PRIMARY_COLOR: str = "#6366f1"
    SECONDARY_COLOR: str = "#8b5cf6"
    ACCENT_COLOR: str = "#bb86fc"
    BACKGROUND_COLOR: str = "#1a1c1e"
    SURFACE_COLOR: str = "#2d3033"
    ERROR_COLOR: str = "#f44336"
    SUCCESS_COLOR: str = "#4caf50"
    WARNING_COLOR: str = "#ff9800"


config = Config()
