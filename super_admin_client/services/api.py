import httpx

class ApiClient:
    def __init__(self, base_url="http://localhost:8000/api/v1"):
        self.base_url = base_url
        self.token = None
        self._client = httpx.Client(timeout=10.0)  # Shared client with timeout

    def set_token(self, token):
        self.token = token

    def _get_headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def login(self, username, password):
        try:
            res = self._client.post(f"{self.base_url}/auth/token", data={
                "username": username,
                "password": password
            })
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Login error: {e}")
            return None

    def get_tenants(self):
        try:
            res = self._client.get(f"{self.base_url}/tenants/", headers=self._get_headers())
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Get tenants error: {e}")
            return []

    def get_plans(self):
        try:
            res = self._client.get(f"{self.base_url}/tenants/plans", headers=self._get_headers())
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Get plans error: {e}")
            return []

    def create_tenant(self, name, subscription_plan_id, domain=None):
        try:
            res = self._client.post(
                f"{self.base_url}/tenants/",
                headers=self._get_headers(),
                json={
                    "name": name,
                    "subscription_plan_id": subscription_plan_id,
                    "domain": domain,
                },
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Create tenant error: {e}")
            return None

    # ===================
    # SuperAdmin API
    # ===================

    def get_system_stats(self):
        """Get system-wide statistics."""
        try:
            res = self._client.get(f"{self.base_url}/super-admin/stats", headers=self._get_headers())
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Get stats error: {e}")
            return None

    def get_all_tenants(self, page: int = 1, page_size: int = 20):
        """Get all tenants with pagination."""
        try:
            res = self._client.get(
                f"{self.base_url}/super-admin/tenants",
                headers=self._get_headers(),
                params={"page": page, "page_size": page_size},
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Get all tenants error: {e}")
            return {"items": [], "total": 0}

    def suspend_tenant(self, tenant_id: str, reason: str):
        """Suspend a tenant."""
        try:
            res = self._client.post(
                f"{self.base_url}/super-admin/tenants/{tenant_id}/suspend",
                headers=self._get_headers(),
                json={"tenant_id": tenant_id, "reason": reason},
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Suspend tenant error: {e}")
            return None

    def reactivate_tenant(self, tenant_id: str):
        """Reactivate a suspended tenant."""
        try:
            res = self._client.post(
                f"{self.base_url}/super-admin/tenants/{tenant_id}/reactivate",
                headers=self._get_headers(),
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Reactivate tenant error: {e}")
            return None

    def get_tenant_settings(self, tenant_id: str):
        """Get settings overview for a tenant."""
        try:
            res = self._client.get(
                f"{self.base_url}/super-admin/tenants/{tenant_id}/settings",
                headers=self._get_headers(),
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Get tenant settings error: {e}")
            return None

    def set_tenant_branding(self, tenant_id: str, branding: dict):
        """Set branding for a tenant."""
        try:
            res = self._client.put(
                f"{self.base_url}/super-admin/tenants/{tenant_id}/branding",
                headers=self._get_headers(),
                json=branding,
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Set tenant branding error: {e}")
            return None

    def create_subscription_plan(self, plan_data: dict):
        """Create a new subscription plan."""
        try:
            res = self._client.post(
                f"{self.base_url}/super-admin/subscription-plans",
                headers=self._get_headers(),
                json=plan_data,
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Create plan error: {e}")
            return None

    def get_subscription_plans(self):
        """Get all subscription plans."""
        try:
            res = self._client.get(
                f"{self.base_url}/super-admin/subscription-plans",
                headers=self._get_headers(),
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Get plans error: {e}")
            return []

    def delete_subscription_plan(self, plan_id: str):
        """Delete a subscription plan."""
        try:
            res = self._client.delete(
                f"{self.base_url}/super-admin/subscription-plans/{plan_id}",
                headers=self._get_headers(),
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Delete plan error: {e}")
            return None

    def check_database_health(self):
        """Check database health."""
        try:
            res = self._client.get(
                f"{self.base_url}/super-admin/database/health",
                headers=self._get_headers(),
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Database health check error: {e}")
            return {"status": "error", "error": str(e)}


api_client = ApiClient()
