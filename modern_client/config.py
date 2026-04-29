import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
    APP_TITLE = "Retail POS - Modern"
    THEME_MODE = "dark"
    TERMINAL_ID = os.getenv("TERMINAL_ID", "POS-1")

settings = Settings()
