"""API client for Super Admin Portal.

This module provides all HTTP communication with the backend API.
Uses the correct super-admin endpoints for production-ready integration.
"""
from __future__ import annotations

from typing import Any
import httpx

from config import config
from services.auth import auth_service


class ApiClient:
    """HTTP API client for Super Admin operations."""
    
    def __init__(self, base_url: str = config.API_BASE_URL, timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout
    
    def _get_headers(self) -> dict:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        headers.update(auth_service.get_headers())
        return headers
    
    def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
        data: dict | None = None,
    ) -> dict | list | None:
        """Make HTTP request with error handling."""
        url = f"{self.base_url}{path}"
        try:
            response = httpx.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                json=json,
                params=params,
                data=data,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            # Handle empty responses
            if response.status_code == 204:
                return {"success": True}
            
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error {e.response.status_code}: {e.response.text}")
            # Return error details for UI handling
            try:
                return {"error": True, "status_code": e.response.status_code, "detail": e.response.json().get("detail", str(e))}
            except Exception:
                return {"error": True, "status_code": e.response.status_code, "detail": str(e)}
        except httpx.RequestError as e:
            print(f"Request error: {e}")
            return {"error": True, "detail": f"Connection error: {e}"}
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {"error": True, "detail": str(e)}
    
    # ==========================================
    # Authentication
    # ==========================================
    
    def login(self, username: str, password: str) -> dict | None:
        """Authenticate user and obtain tokens."""
        try:
            response = httpx.post(
                f"{self.base_url}/auth/token",
                data={"username": username, "password": password},
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            
            if "access_token" in result:
                auth_service.set_tokens(
                    access_token=result["access_token"],
                    refresh_token=result.get("refresh_token"),
                )
            return result
        except Exception as e:
            print(f"Login error: {e}")
            return None
    
    def logout(self) -> None:
        """Clear authentication tokens."""
        auth_service.clear_tokens()
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return auth_service.is_authenticated()
    
    def is_super_admin(self) -> bool:
        """Check if user is super admin."""
        return auth_service.is_super_admin()
    
    def get_current_user(self) -> dict | None:
        """Get current user info from token."""
        return auth_service.user_info
    
    # ==========================================
    # System Stats & Health
    # ==========================================
    
    def get_system_stats(self) -> dict | None:
        """Get system-wide statistics.
        
        Returns:
            dict with total_tenants, active_tenants, total_users, 
            active_users, total_sales_all_time, total_revenue_all_time
        """
        return self._request("GET", "/super-admin/stats")
    
    def check_database_health(self) -> dict:
        """Check database health and statistics.
        
        Returns:
            dict with status, connected, table_counts, checked_at
        """
        result = self._request("GET", "/super-admin/database/health")
        return result or {"status": "error", "connected": False}
    
    def get_pci_compliance(self) -> dict | None:
        """Get PCI-DSS compliance check results.
        
        Returns:
            dict with is_compliant, critical_issues, warnings, 
            passed_checks, checked_at
        """
        return self._request("GET", "/super-admin/compliance")
    
    def get_detailed_health(self) -> dict:
        """Get detailed system health including Celery.
        
        Returns:
            dict with status, components (api, celery, database)
        """
        result = self._request("GET", "/monitoring/health/detailed")
        return result or {"status": "error"}
    
    def get_celery_workers(self) -> dict:
        """Get list of active Celery workers.
        
        Returns:
            dict with status, workers, count
        """
        result = self._request("GET", "/monitoring/celery/workers")
        return result or {"status": "no_workers", "workers": [], "count": 0}
    
    def get_celery_queues(self) -> dict:
        """Get Celery queue statistics."""
        result = self._request("GET", "/monitoring/celery/queues")
        return result or {"queues": {}}
    
    # ==========================================
    # Tenant Management
    # ==========================================
    
    def get_all_tenants(
        self, 
        page: int = 1, 
        page_size: int = 20, 
        active_only: bool = False
    ) -> dict:
        """Get paginated list of all tenants.
        
        Uses the correct /super-admin/tenants endpoint.
        
        Returns:
            dict with items, total, page, page_size
        """
        result = self._request(
            "GET",
            "/super-admin/tenants",
            params={"page": page, "page_size": page_size, "active_only": active_only},
        )
        return result or {"items": [], "total": 0, "page": page, "page_size": page_size}
    
    def get_tenant_details(self, tenant_id: str) -> dict | None:
        """Get detailed tenant information."""
        # Use settings endpoint for now - could add dedicated endpoint
        return self._request("GET", f"/super-admin/tenants/{tenant_id}/settings")
    
    def suspend_tenant(self, tenant_id: str, reason: str) -> dict | None:
        """Suspend a tenant (disable all access).
        
        Args:
            tenant_id: ID of tenant to suspend
            reason: Reason for suspension (min 10 chars)
        """
        return self._request(
            "POST",
            f"/super-admin/tenants/{tenant_id}/suspend",
            json={"tenant_id": tenant_id, "reason": reason},
        )
    
    def reactivate_tenant(self, tenant_id: str) -> dict | None:
        """Reactivate a suspended tenant."""
        return self._request(
            "POST",
            f"/super-admin/tenants/{tenant_id}/reactivate",
        )
    
    def get_tenant_settings(self, tenant_id: str) -> dict | None:
        """Get settings overview for a tenant."""
        return self._request("GET", f"/super-admin/tenants/{tenant_id}/settings")
    
    def set_tenant_branding(self, tenant_id: str, branding: dict) -> dict | None:
        """Set/update branding for a tenant.
        
        Args:
            tenant_id: Tenant ID
            branding: dict with logo_url, primary_color, secondary_color, 
                     accent_color, company_name, company_tagline
        """
        return self._request(
            "PUT",
            f"/super-admin/tenants/{tenant_id}/branding",
            json=branding,
        )
    
    def reset_tenant_settings(self, tenant_id: str) -> dict | None:
        """Reset tenant settings to defaults."""
        return self._request(
            "POST",
            f"/super-admin/tenants/{tenant_id}/settings/reset",
        )
    
    def create_tenant(
        self, 
        name: str, 
        subscription_plan_id: str, 
        domain: str | None = None
    ) -> dict | None:
        """Create a new tenant.
        
        Note: Uses /tenants/ endpoint (tenants_router)
        """
        return self._request(
            "POST",
            "/tenants/",
            json={
                "name": name,
                "subscription_plan_id": subscription_plan_id,
                "domain": domain,
            },
        )
    
    # ==========================================
    # Subscription Plans
    # ==========================================
    
    def get_subscription_plans(self) -> list:
        """Get all subscription plans.
        
        Uses the correct /super-admin/subscription-plans endpoint.
        """
        result = self._request("GET", "/super-admin/subscription-plans")
        return result if isinstance(result, list) else []
    
    def create_subscription_plan(self, plan_data: dict) -> dict | None:
        """Create a new subscription plan.
        
        Args:
            plan_data: dict with name, description, price_monthly, price_annual,
                      max_users, max_products, max_locations, features, is_active
        """
        return self._request(
            "POST",
            "/super-admin/subscription-plans",
            json=plan_data,
        )
    
    def delete_subscription_plan(self, plan_id: str) -> dict | None:
        """Delete a subscription plan.
        
        Note: Cannot delete if tenants are using the plan.
        """
        return self._request("DELETE", f"/super-admin/subscription-plans/{plan_id}")
    
    # ==========================================
    # Analytics
    # ==========================================
    
    def get_sales_trends(
        self, 
        period_type: str = "daily",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict | None:
        """Get sales trends over time.
        
        Args:
            period_type: daily, weekly, or monthly
            start_date: ISO date string
            end_date: ISO date string
        """
        params = {"period_type": period_type}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._request("GET", "/analytics/sales/trends", params=params)
    
    def get_dashboard_summary(self) -> dict | None:
        """Get complete dashboard summary."""
        return self._request("GET", "/analytics/dashboard/summary")
    
    def get_top_products(self, period: str = "month", limit: int = 10) -> dict | None:
        """Get top selling products."""
        return self._request(
            "GET", 
            "/analytics/products/top",
            params={"period": period, "limit": limit},
        )
    
    # ==========================================
    # GDPR Compliance
    # ==========================================
    
    def get_gdpr_export_requests(self, status: str | None = None) -> list:
        """Get data export requests across tenants."""
        params = {}
        if status:
            params["status"] = status
        result = self._request("GET", "/gdpr/exports", params=params)
        return result if isinstance(result, list) else []
    
    def get_gdpr_erasure_requests(self, status: str | None = None) -> list:
        """Get erasure requests across tenants."""
        params = {}
        if status:
            params["status"] = status
        result = self._request("GET", "/gdpr/erasures", params=params)
        return result if isinstance(result, list) else []
    
    # ==========================================
    # Webhooks
    # ==========================================
    
    def get_webhook_subscriptions(self) -> list:
        """Get all webhook subscriptions."""
        result = self._request("GET", "/webhooks/subscriptions")
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return result if isinstance(result, list) else []
    
    def get_webhook_event_types(self) -> dict:
        """Get available webhook event types."""
        result = self._request("GET", "/webhooks/event-types")
        return result or {"event_types": []}
    
    def create_webhook_subscription(self, data: dict) -> dict | None:
        """Create a webhook subscription.
        
        Args:
            data: dict with name, url, events, headers, description
        """
        return self._request("POST", "/webhooks/subscriptions", json=data)
    
    def delete_webhook_subscription(self, webhook_id: str) -> dict | None:
        """Delete a webhook subscription."""
        return self._request("DELETE", f"/webhooks/subscriptions/{webhook_id}")
    
    def test_webhook(self, webhook_id: str) -> dict | None:
        """Test a webhook subscription."""
        return self._request("POST", f"/webhooks/subscriptions/{webhook_id}/test")
    
    # ==========================================
    # Reports
    # ==========================================
    
    def get_report_definitions(self) -> list:
        """Get all report definitions."""
        result = self._request("GET", "/reports/definitions")
        return result if isinstance(result, list) else []
    
    def create_report_definition(self, data: dict) -> dict | None:
        """Create a custom report definition."""
        return self._request("POST", "/reports/definitions", json=data)
    
    def generate_report(self, definition_id: str, format: str = "json") -> dict | None:
        """Generate a report from definition."""
        return self._request(
            "POST",
            "/reports/generate",
            json={"definition_id": definition_id, "format": format},
        )
    
    # ==========================================
    # API Keys (Read-only for Super Admin)
    # ==========================================
    
    def get_api_keys(self, tenant_id: str | None = None) -> list:
        """Get API keys (optionally filtered by tenant)."""
        params = {}
        if tenant_id:
            params["tenant_id"] = tenant_id
        result = self._request("GET", "/api-keys", params=params)
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return result if isinstance(result, list) else []
    
    # ==========================================
    # Legacy compatibility methods
    # (These redirect to correct endpoints)
    # ==========================================
    
    def get_tenants(self) -> list:
        """Legacy method - redirects to get_all_tenants.
        
        DEPRECATED: Use get_all_tenants() instead.
        """
        result = self.get_all_tenants()
        return result.get("items", []) if isinstance(result, dict) else []
    
    def get_plans(self) -> list:
        """Legacy method - redirects to get_subscription_plans.
        
        DEPRECATED: Use get_subscription_plans() instead.
        """
        return self.get_subscription_plans()
    
    def set_token(self, token: str) -> None:
        """Legacy method for setting token.
        
        DEPRECATED: Use login() or auth_service directly.
        """
        auth_service.set_tokens(token)


# Global API client instance
api_client = ApiClient()
