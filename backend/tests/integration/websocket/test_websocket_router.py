"""
Tests for WebSocket router.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
import jwt

from app.api.main import app
from app.core.settings import get_settings


@pytest.fixture
def test_client():
    """Fixture to provide a test client."""
    return TestClient(app)


@pytest.fixture
def valid_token():
    """Fixture to provide a valid JWT token."""
    settings = get_settings()
    payload = {
        "sub": "user123",
        "username": "john_doe",
        "role": "cashier",
        "tenant_id": "tenant1",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


class TestWebSocketRouter:
    """Tests for WebSocket router endpoints."""

    def test_websocket_stats_endpoint(self, test_client):
        """Test GET /api/v1/ws/stats endpoint."""
        response = test_client.get("/api/v1/ws/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_connections" in data
        assert "total_tenants" in data
        assert "tenant_stats" in data

    def test_websocket_connected_users_endpoint(self, test_client):
        """Test GET /api/v1/ws/connected-users endpoint."""
        response = test_client.get("/api/v1/ws/connected-users?tenant_id=tenant1")
        assert response.status_code == 200
        data = response.json()
        assert "tenant_id" in data
        assert "users" in data
        assert data["tenant_id"] == "tenant1"
