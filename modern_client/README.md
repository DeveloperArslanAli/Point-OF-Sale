# Modern Retail POS Client

A stylish, modern Point of Sale interface built with [Flet](https://flet.dev) (Python).

## Features
- **Modern UI**: Dark mode, responsive design, smooth animations.
- **POS Terminal**: Product grid, cart management, quick pay.
- **Dashboard**: Real-time sales statistics.
- **Pure Python**: No JavaScript required.

## Setup

1. **Install Dependencies**:
   ```bash
   



   poetry install
   ```

2. **Run the App**:
   ```bash
   poetry run python main.py
   ```

## Structure
- `main.py`: Entry point and routing.
- `views/`: UI screens (Login, Dashboard, POS).
- `components/`: Reusable widgets (Sidebar, ProductCard).

## Backend Connection
Currently mocks authentication and data. Update `services/api.py` (to be created) to connect to the FastAPI backend.
