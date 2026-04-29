"""Integration tests for customer engagement API endpoints."""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


async def _register_and_login(
    async_session,
    client: AsyncClient,
    *,
    role: UserRole = UserRole.MANAGER,
    label: str | None = None,
) -> str:
    prefix = label or f"user_{uuid4().hex[:6]}"
    return await login_as(async_session, client, role, email_prefix=prefix)


async def _create_customer(
    client: AsyncClient,
    token: str,
    *,
    email: str | None = None,
    first_name: str = "Jane",
    last_name: str = "Doe",
    phone: str = "+15551234",
) -> dict:
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email or f"{uuid4().hex[:8]}@example.com",
        "phone": phone,
    }
    resp = await client.post(
        "/api/v1/customers",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def client() -> AsyncClient:
    """Create test client."""
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================================
# Campaign Endpoint Tests
# ============================================================================


class TestCampaignEndpoints:
    """Tests for marketing campaign endpoints."""

    @pytest.mark.asyncio
    async def test_create_campaign_success(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test creating a marketing campaign."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)

        payload = {
            "name": f"Summer Sale {uuid4().hex[:6]}",
            "description": "Big summer discount campaign",
            "campaign_type": "email",
            "trigger": "manual",
            "content": {
                "subject": "Summer Sale - 20% Off!",
                "body": "Dear customer, enjoy 20% off on all products this summer!",
            },
        }

        resp = await client.post(
            "/api/v1/engagement/campaigns",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, resp.text

        data = resp.json()
        assert data["name"] == payload["name"]
        assert data["campaign_type"] == "email"
        assert data["status"] == "draft"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_campaign_cashier_forbidden(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test that cashiers cannot create campaigns."""
        token = await _register_and_login(async_session, client, role=UserRole.CASHIER)

        payload = {
            "name": "Unauthorized Campaign",
            "campaign_type": "email",
        }

        resp = await client.post(
            "/api/v1/engagement/campaigns",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_campaigns(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test listing campaigns."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)

        # Create a campaign first
        create_resp = await client.post(
            "/api/v1/engagement/campaigns",
            json={
                "name": f"Test Campaign {uuid4().hex[:6]}",
                "campaign_type": "email",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201

        # List campaigns
        resp = await client.get(
            "/api/v1/engagement/campaigns",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_get_campaign_by_id(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test getting a campaign by ID."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)

        # Create a campaign
        create_resp = await client.post(
            "/api/v1/engagement/campaigns",
            json={
                "name": f"Test Campaign {uuid4().hex[:6]}",
                "campaign_type": "sms",
                "description": "Test description",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        campaign_id = create_resp.json()["id"]

        # Get by ID
        resp = await client.get(
            f"/api/v1/engagement/campaigns/{campaign_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["id"] == campaign_id
        assert data["campaign_type"] == "sms"

    @pytest.mark.asyncio
    async def test_update_campaign(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test updating a campaign."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)

        # Create a campaign
        create_resp = await client.post(
            "/api/v1/engagement/campaigns",
            json={
                "name": f"Original Name {uuid4().hex[:6]}",
                "campaign_type": "email",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        campaign_id = create_resp.json()["id"]

        # Update it
        resp = await client.put(
            f"/api/v1/engagement/campaigns/{campaign_id}",
            json={
                "name": "Updated Name",
                "description": "New description",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New description"


# ============================================================================
# Feedback Endpoint Tests
# ============================================================================


class TestFeedbackEndpoints:
    """Tests for customer feedback endpoints."""

    @pytest.mark.asyncio
    async def test_submit_feedback_review(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test submitting a review."""
        token = await _register_and_login(async_session, client, role=UserRole.CASHIER)

        # Create a customer first
        customer = await _create_customer(client, token)

        payload = {
            "customer_id": customer["id"],
            "feedback_type": "review",
            "subject": "Great service!",
            "message": "I loved the shopping experience. Very helpful staff.",
            "rating": 5,
        }

        resp = await client.post(
            "/api/v1/engagement/feedback",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, resp.text

        data = resp.json()
        assert data["feedback_type"] == "review"
        assert data["rating"] == 5
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_submit_feedback_complaint(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test submitting a complaint."""
        token = await _register_and_login(async_session, client, role=UserRole.CASHIER)
        customer = await _create_customer(client, token)

        payload = {
            "customer_id": customer["id"],
            "feedback_type": "complaint",
            "subject": "Product quality issue",
            "message": "The product I received was damaged.",
            "rating": 1,
        }

        resp = await client.post(
            "/api/v1/engagement/feedback",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201

        data = resp.json()
        assert data["feedback_type"] == "complaint"
        assert data["rating"] == 1

    @pytest.mark.asyncio
    async def test_respond_to_feedback(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test responding to feedback."""
        # Cashier submits feedback
        cashier_token = await _register_and_login(
            async_session, client, role=UserRole.CASHIER, label="cashier"
        )
        customer = await _create_customer(client, cashier_token)

        feedback_resp = await client.post(
            "/api/v1/engagement/feedback",
            json={
                "customer_id": customer["id"],
                "feedback_type": "question",
                "message": "Do you have this in blue?",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert feedback_resp.status_code == 201
        feedback_id = feedback_resp.json()["id"]

        # Manager responds
        manager_token = await _register_and_login(
            async_session, client, role=UserRole.MANAGER, label="manager"
        )

        resp = await client.post(
            f"/api/v1/engagement/feedback/{feedback_id}/respond",
            json={"response": "Yes, we have it in blue. It will be available next week."},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["response"] is not None
        assert "blue" in data["response"]

    @pytest.mark.asyncio
    async def test_list_feedback(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test listing feedback with filters."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)
        customer = await _create_customer(client, token)

        # Submit some feedback
        await client.post(
            "/api/v1/engagement/feedback",
            json={
                "customer_id": customer["id"],
                "feedback_type": "review",
                "message": "Test review",
                "rating": 4,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # List all feedback
        resp = await client.get(
            "/api/v1/engagement/feedback",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "items" in data


# ============================================================================
# Notification Preferences Tests
# ============================================================================


class TestNotificationPreferencesEndpoints:
    """Tests for notification preferences endpoints."""

    @pytest.mark.asyncio
    async def test_get_customer_preferences(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test getting customer notification preferences."""
        token = await _register_and_login(async_session, client, role=UserRole.CASHIER)
        customer = await _create_customer(client, token)

        resp = await client.get(
            f"/api/v1/engagement/customers/{customer['id']}/preferences",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        data = resp.json()
        # Check default preferences are returned
        assert "email_enabled" in data
        assert "sms_enabled" in data
        assert "marketing_enabled" in data

    @pytest.mark.asyncio
    async def test_update_customer_preferences(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test updating customer notification preferences."""
        token = await _register_and_login(async_session, client, role=UserRole.CASHIER)
        customer = await _create_customer(client, token)

        # Update preferences
        resp = await client.put(
            f"/api/v1/engagement/customers/{customer['id']}/preferences",
            json={
                "email_enabled": True,
                "sms_enabled": True,
                "marketing_enabled": False,
                "quiet_hours_start": 22,
                "quiet_hours_end": 8,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["email_enabled"] is True
        assert data["sms_enabled"] is True
        assert data["marketing_enabled"] is False
        assert data["quiet_hours_start"] == 22


# ============================================================================
# Engagement Profile Tests
# ============================================================================


class TestEngagementProfileEndpoints:
    """Tests for engagement profile endpoints."""

    @pytest.mark.asyncio
    async def test_get_customer_engagement_profile(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test getting customer engagement profile."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)
        customer = await _create_customer(client, token)

        resp = await client.get(
            f"/api/v1/engagement/customers/{customer['id']}/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Profile may not exist yet for new customer
        assert resp.status_code in (200, 404)

        if resp.status_code == 200:
            data = resp.json()
            assert "segment" in data
            assert "total_purchases" in data

    @pytest.mark.asyncio
    async def test_get_segment_stats(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test getting segment statistics."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)

        resp = await client.get(
            "/api/v1/engagement/segments",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert isinstance(data, dict)
        # Should have segment counts

    @pytest.mark.asyncio
    async def test_get_engagement_dashboard(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test getting engagement dashboard."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)

        resp = await client.get(
            "/api/v1/engagement/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "segment_distribution" in data
        assert "total_customers" in data


# ============================================================================
# Campaign Lifecycle Tests
# ============================================================================


class TestCampaignLifecycle:
    """Tests for campaign lifecycle operations."""

    @pytest.mark.asyncio
    async def test_campaign_schedule(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test scheduling a campaign."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)

        # Create campaign
        create_resp = await client.post(
            "/api/v1/engagement/campaigns",
            json={
                "name": f"Scheduled Campaign {uuid4().hex[:6]}",
                "campaign_type": "email",
                "content": {
                    "subject": "Test Subject",
                    "body": "Test body content",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        campaign_id = create_resp.json()["id"]

        # Schedule it
        resp = await client.post(
            f"/api/v1/engagement/campaigns/{campaign_id}/schedule",
            json={"scheduled_at": "2025-12-25T10:00:00Z"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "scheduled"

    @pytest.mark.asyncio
    async def test_campaign_start_and_pause(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test starting and pausing a campaign."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)

        # Create campaign
        create_resp = await client.post(
            "/api/v1/engagement/campaigns",
            json={
                "name": f"Start Test {uuid4().hex[:6]}",
                "campaign_type": "email",
                "content": {
                    "subject": "Test",
                    "body": "Body",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        campaign_id = create_resp.json()["id"]

        # Start it
        start_resp = await client.post(
            f"/api/v1/engagement/campaigns/{campaign_id}/start",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert start_resp.status_code == 200
        assert start_resp.json()["status"] == "running"

        # Pause it
        pause_resp = await client.post(
            f"/api/v1/engagement/campaigns/{campaign_id}/pause",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pause_resp.status_code == 200
        assert pause_resp.json()["status"] == "paused"

    @pytest.mark.asyncio
    async def test_campaign_cancel(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test cancelling a campaign."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)

        # Create campaign
        create_resp = await client.post(
            "/api/v1/engagement/campaigns",
            json={
                "name": f"Cancel Test {uuid4().hex[:6]}",
                "campaign_type": "sms",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code == 201
        campaign_id = create_resp.json()["id"]

        # Cancel it
        resp = await client.post(
            f"/api/v1/engagement/campaigns/{campaign_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"


# ============================================================================
# Public Reviews Tests
# ============================================================================


class TestPublicReviews:
    """Tests for public reviews endpoint."""

    @pytest.mark.asyncio
    async def test_get_public_reviews_requires_auth(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test that public reviews endpoint requires authentication."""
        resp = await client.get("/api/v1/engagement/feedback/public/reviews")
        # Should require auth
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_get_public_reviews_filtered(
        self,
        async_session,
        client: AsyncClient,
    ) -> None:
        """Test getting public reviews with min rating filter."""
        token = await _register_and_login(async_session, client, role=UserRole.MANAGER)

        resp = await client.get(
            "/api/v1/engagement/feedback/public/reviews?min_rating=4",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert isinstance(data["items"], list)
