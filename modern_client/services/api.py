from typing import Any, Callable

import httpx

from config import settings


class ApiService:
    def __init__(self) -> None:
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.last_error_message: str | None = None
        self.last_error_status: int | None = None
        self.client = httpx.Client(
            base_url=settings.API_BASE_URL.rstrip("/"),
            timeout=httpx.Timeout(15.0),
            headers={"Accept": "application/json"},
        )
        self.error_handler: Callable[[str], None] | None = None

    def set_error_handler(self, handler: Callable[[str], None]) -> None:
        self.error_handler = handler

    def _handle_error(self, context: str, error: Exception) -> None:
        self.last_error_status = None
        self.last_error_message = None

        message = f"{context}: {error}"
        status_code: int | None = None

        if isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            detail: str | None = None
            try:
                body = error.response.json()
                if isinstance(body, dict):
                    detail = body.get("detail") or body.get("message")
                    code = body.get("code")
                    if code and detail:
                        detail = f"{detail} ({code})"
                    elif code:
                        detail = code
            except Exception:
                detail = error.response.text[:200]
            message = f"{context}: {status_code} {detail or error}"

        self.last_error_status = status_code
        self.last_error_message = message

        print(message)
        if self.error_handler:
            self.error_handler(message)

    def set_tokens(self, access_token: str | None, refresh_token: str | None = None) -> None:
        self.access_token = access_token
        if refresh_token is not None:
            self.refresh_token = refresh_token

        if access_token:
            self.client.headers["Authorization"] = f"Bearer {access_token}"
        elif "Authorization" in self.client.headers:
            self.client.headers.pop("Authorization")

    # Backwards-compatible alias
    def set_token(self, token: str) -> None:
        self.set_tokens(token)

    def _refresh_tokens(self) -> bool:
        if not self.refresh_token:
            return False

        # Avoid sending a stale Authorization header when refreshing
        self.client.headers.pop("Authorization", None)
        try:
            response = self.client.post("/auth/refresh", json={"refresh_token": self.refresh_token})
            response.raise_for_status()
            data = response.json()
            self.set_tokens(data.get("access_token"), data.get("refresh_token", self.refresh_token))
            return True
        except httpx.HTTPError as exc:
            self._handle_error("Token refresh failed", exc)
            self.access_token = None
            self.refresh_token = None
            return False
        finally:
            if self.access_token:
                self.client.headers["Authorization"] = f"Bearer {self.access_token}"

    def _request(self, method: str, url: str, *, retry_on_401: bool = True, **kwargs: Any) -> Any:
        try:
            response = self.client.request(method, url, **kwargs)
            if response.status_code == 401 and retry_on_401 and self._refresh_tokens():
                response = self.client.request(method, url, **kwargs)

            response.raise_for_status()
            self.last_error_message = None
            self.last_error_status = None
            if response.status_code == 204:
                return None
            return response.json()
        except httpx.HTTPStatusError as exc:
            self._handle_error(f"{method} {url} failed", exc)
        except httpx.HTTPError as exc:
            self._handle_error(f"{method} {url} failed", exc)
        return None

    def _request_allow_404(self, method: str, url: str, *, retry_on_401: bool = True, **kwargs: Any) -> Any:
        """Variant of _request that treats HTTP 404 as an expected "not found" result."""
        try:
            response = self.client.request(method, url, **kwargs)
            if response.status_code == 401 and retry_on_401 and self._refresh_tokens():
                response = self.client.request(method, url, **kwargs)

            if response.status_code == 404:
                self.last_error_status = None
                self.last_error_message = None
                return None

            response.raise_for_status()
            self.last_error_message = None
            self.last_error_status = None
            if response.status_code == 204:
                return None
            return response.json()
        except httpx.HTTPStatusError as exc:
            self._handle_error(f"{method} {url} failed", exc)
        except httpx.HTTPError as exc:
            self._handle_error(f"{method} {url} failed", exc)
        return None

    # ========== Auth ==========
    def login(self, email: str, password: str) -> dict | None:
        payload = {"email": email, "password": password}
        data = self._request("POST", "/auth/login", json=payload, retry_on_401=False)
        if data and data.get("access_token"):
            self.set_tokens(data.get("access_token"), data.get("refresh_token"))
        return data

    def logout(self) -> bool:
        if not self.refresh_token:
            return True
        payload = {"refresh_token": self.refresh_token}
        result = self._request("POST", "/auth/logout", json=payload, retry_on_401=False)
        if result is not None:
            self.set_tokens(None, None)
            return True
        return False

    def me(self) -> dict | None:
        return self._request("GET", "/auth/me")

    # ========== Products ==========
    def get_products(self, search: str | None = None, category_id: str | None = None, active: bool | None = None, limit: int = 100) -> list:
        params: dict[str, Any] = {"limit": limit}
        if search:
            params["search"] = search
        if category_id:
            params["category_id"] = category_id
        if active is not None:
            params["active"] = str(active).lower()

        data = self._request("GET", "/products", params=params)
        return data.get("items", []) if isinstance(data, dict) else []

    def create_product(self, product_data: dict) -> dict | None:
        return self._request("POST", "/products", json=product_data)

    def update_product(self, product_id: str, product_data: dict) -> dict | None:
        return self._request("PATCH", f"/products/{product_id}", json=product_data)

    def delete_product(self, product_id: str, version: int) -> bool:
        result = self._request("POST", f"/products/{product_id}/deactivate", json={"expected_version": version})
        return result is not None

    def record_inventory_movement(self, product_id: str, quantity: int, reason: str = "Initial Stock") -> dict | None:
        payload = {"quantity": quantity, "direction": "in", "reason": reason}
        return self._request("POST", f"/inventory/products/{product_id}/movements", json=payload)

    # ========== Dashboard ==========
    def get_dashboard_stats(self) -> dict | None:
        try:
            stats = {"total_sales": "$0.00", "orders": "0", "customers": "0", "inventory": "0 Items", "recent_sales": []}

            products_data = self._request("GET", "/products", params={"limit": 1}) or {}
            stats["inventory"] = f"{products_data.get('meta', {}).get('total', 0)} Items"

            customers_data = self._request("GET", "/customers", params={"limit": 1}) or {}
            stats["customers"] = str(customers_data.get("meta", {}).get("total", 0))

            sales_data = self._request("GET", "/sales", params={"limit": 100}) or {}
            items = sales_data.get("items", []) if isinstance(sales_data, dict) else []
            total_count = sales_data.get("meta", {}).get("total", len(items)) if isinstance(sales_data, dict) else len(items)
            stats["orders"] = str(total_count)
            total_amount = sum(float(sale.get("total_amount", 0)) for sale in items)
            stats["total_sales"] = f"${total_amount:,.2f}"
            stats["recent_sales"] = items[:5]

            return stats
        except Exception as exc:
            self._handle_error("Fetch dashboard stats failed", exc)
            return None

    # ========== Customers ==========
    def get_customers(self, search: str | None = None, active: bool | None = None, limit: int = 100) -> list:
        params: dict[str, Any] = {"limit": limit}
        if search:
            params["search"] = search
        if active is not None:
            params["active"] = str(active).lower()

        data = self._request("GET", "/customers", params=params)
        return data.get("items", []) if isinstance(data, dict) else []

    def create_customer(self, customer_data: dict) -> dict | None:
        return self._request("POST", "/customers", json=customer_data)

    def update_customer(self, customer_id: str, customer_data: dict) -> dict | None:
        return self._request("PATCH", f"/customers/{customer_id}", json=customer_data)

    def delete_customer(self, customer_id: str, version: int) -> bool:
        result = self._request("POST", f"/customers/{customer_id}/deactivate", json={"expected_version": version})
        return result is not None

    # ========== Sales ==========
    def get_sales(self, limit: int | None = None) -> list:
        params = {"limit": limit} if limit else None
        data = self._request("GET", "/sales", params=params)
        return data.get("items", []) if isinstance(data, dict) else []

    def create_sale(self, sale_data: dict) -> dict | None:
        return self._request("POST", "/sales", json=sale_data)

    def get_sale(self, sale_id: str) -> dict | None:
        return self._request("GET", f"/sales/{sale_id}")

    # ========== Returns ==========
    def create_return(self, return_data: dict) -> dict | None:
        return self._request("POST", "/returns", json=return_data)

    def get_returns(self, limit: int = 20) -> list:
        data = self._request("GET", "/returns", params={"limit": limit})
        return data.get("items", []) if isinstance(data, dict) else []

    # ========== Employees ==========
    def get_employees(self, search: str | None = None, active: bool | None = None, limit: int = 20) -> list:
        params: dict[str, Any] = {"limit": limit}
        if search:
            params["search"] = search
        if active is not None:
            params["active"] = str(active).lower()

        data = self._request("GET", "/employees", params=params)
        return data.get("items", []) if isinstance(data, dict) else []

    def create_employee(self, data: dict) -> dict | None:
        return self._request("POST", "/employees", json=data)

    def update_employee(self, employee_id: str, data: dict) -> dict | None:
        return self._request("PATCH", f"/employees/{employee_id}", json=data)

    def grant_increment(self, employee_id: str, data: dict) -> dict | None:
        return self._request("POST", f"/employees/{employee_id}/increment", json=data)

    def give_bonus(self, employee_id: str, data: dict) -> dict | None:
        return self._request("POST", f"/employees/{employee_id}/bonus", json=data)

    def get_financial_history(self, employee_id: str) -> dict | None:
        return self._request("GET", f"/employees/{employee_id}/financial-history")

    # ========== Users ==========
    def get_users(self, search: str | None = None, role: str | None = None, active: bool | None = None, limit: int = 20) -> list:
        params: dict[str, Any] = {"limit": limit}
        if search:
            params["search"] = search
        if role:
            params["role"] = role
        if active is not None:
            params["active"] = str(active).lower()

        data = self._request("GET", "/auth/users", params=params)
        return data.get("items", []) if isinstance(data, dict) else []

    def create_user(self, data: dict) -> dict | None:
        return self._request("POST", "/auth/users", json=data)

    def update_user_role(self, user_id: str, role: str, current_version: int) -> dict | None:
        payload = {"role": role, "expected_version": current_version}
        return self._request("POST", f"/auth/users/{user_id}/role", json=payload)

    def deactivate_user(self, user_id: str, current_version: int) -> dict | None:
        return self._request("POST", f"/auth/users/{user_id}/deactivate", json={"expected_version": current_version})

    def activate_user(self, user_id: str, current_version: int) -> dict | None:
        return self._request("POST", f"/auth/users/{user_id}/activate", json={"expected_version": current_version})

    def reset_user_password(self, user_id: str, new_password: str, current_version: int) -> dict | None:
        payload = {"new_password": new_password, "expected_version": current_version}
        return self._request("POST", f"/auth/users/{user_id}/password", json=payload)

    # ========== Shifts ==========
    def get_active_shift(self) -> dict | None:
        return self._request_allow_404("GET", "/shifts/active")

    def start_shift(self, terminal_id: str, opening_cash: float | None = None, currency: str = "USD", drawer_session_id: str | None = None) -> dict | None:
        payload = {
            "terminal_id": terminal_id,
            "drawer_session_id": drawer_session_id,
            "opening_cash": opening_cash,
            "currency": currency,
        }
        return self._request("POST", "/shifts/start", json=payload)

    def end_shift(self, shift_id: str, closing_cash: float | None = None) -> dict | None:
        payload = {"shift_id": shift_id, "closing_cash": closing_cash}
        return self._request("POST", "/shifts/end", json=payload)

    # ========== Cash Drawer ==========
    def open_cash_drawer(self, terminal_id: str, opening_amount: float, currency: str = "USD") -> dict | None:
        payload = {"terminal_id": terminal_id, "opening_amount": opening_amount, "currency": currency}
        return self._request("POST", "/cash-drawer/open", json=payload)

    def close_cash_drawer(self, session_id: str, closing_amount: float, notes: str | None = None) -> dict | None:
        payload = {"session_id": session_id, "closing_amount": closing_amount, "notes": notes}
        return self._request("POST", "/cash-drawer/close", json=payload)

    def record_cash_movement(self, session_id: str, movement_type: str, amount: float, notes: str | None = None) -> dict | None:
        payload = {"session_id": session_id, "movement_type": movement_type, "amount": amount, "notes": notes}
        return self._request("POST", "/cash-drawer/movements", json=payload)

    def get_cash_drawer(self, session_id: str) -> dict | None:
        return self._request("GET", f"/cash-drawer/{session_id}")

    def get_open_drawer_for_terminal(self, terminal_id: str) -> dict | None:
        return self._request_allow_404("GET", f"/cash-drawer/terminal/{terminal_id}/open")

    # ========== Receipts ==========
    def get_receipts_for_sale(self, sale_id: str) -> dict | None:
        return self._request("GET", f"/receipts/sale/{sale_id}")

    def create_receipt(self, payload: dict) -> dict | None:
        return self._request("POST", "/receipts", json=payload)

    # ========== Payments ==========
    def record_cash_payment(self, sale_id: str, amount: float, currency: str = "USD") -> dict | None:
        payload = {"sale_id": sale_id, "amount": amount, "currency": currency}
        return self._request("POST", "/payments/cash", json=payload)

    def record_card_payment(self, sale_id: str, amount: float, currency: str = "USD", provider: str | None = None) -> dict | None:
        payload = {"sale_id": sale_id, "amount": amount, "currency": currency, "provider": provider}
        return self._request("POST", "/payments/card", json=payload)

    def refund_payment(self, sale_id: str, amount: float, reason: str | None = None) -> dict | None:
        payload = {"sale_id": sale_id, "amount": amount, "reason": reason}
        return self._request("POST", "/payments/refund", json=payload)

    # ========== Inventory Intelligence ==========
    def get_inventory_insights(self) -> dict:
        data = self._request("GET", "/inventory/intelligence")
        return data or {"low_stock": [], "dead_stock": []}

    def get_inventory_abc(self) -> dict:
        data = self._request("GET", "/inventory/intelligence/abc")
        return data or {"classifications": []}

    def get_inventory_forecast(self, product_id: str | None = None) -> dict:
        params: dict[str, Any] = {}
        if product_id:
            params["product_id"] = product_id
        data = self._request("GET", "/inventory/intelligence/forecast", params=params)
        return data or {"forecasts": [], "generated_at": None, "stale": True}

    def get_purchase_suggestions(self) -> dict:
        # Backend endpoint is /po-suggestions
        data = self._request("GET", "/inventory/intelligence/po-suggestions")
        return data or {"suggestions": []}

    def get_vendor_performance(self) -> dict:
        data = self._request("GET", "/inventory/intelligence/vendors")
        return data or {"vendors": [], "generated_at": None}

    def get_po_drafts(self, supplier_id: str | None = None, budget_cap: float | None = None) -> dict:
        params: dict[str, Any] = {}
        if supplier_id:
            params["supplier_id"] = supplier_id
        if budget_cap:
            params["budget_cap"] = str(budget_cap)
        data = self._request("GET", "/inventory/intelligence/po-drafts", params=params)
        return data or {"lines": [], "total_estimated": 0, "generated_at": None}

    def get_advanced_forecast(self, smoothing_alpha: float = 0.3, seasonality: bool = True) -> dict:
        params = {"smoothing_alpha": smoothing_alpha, "use_seasonality": seasonality}
        data = self._request("GET", "/inventory/intelligence/forecast/advanced", params=params)
        return data or {"forecasts": [], "generated_at": None}

    def refresh_inventory_forecast(self, smoothing_alpha: float = 0.3, seasonality: bool = False) -> dict | None:
        payload = {"smoothing_alpha": smoothing_alpha, "seasonality": seasonality}
        return self._request("POST", "/inventory/intelligence/forecast/refresh", json=payload)

    # ===================
    # Settings API
    # ===================

    def get_settings(self) -> dict | None:
        """Get current tenant settings."""
        return self._request("GET", "/settings")

    def update_settings(self, settings: dict) -> dict | None:
        """Update all settings at once."""
        return self._request("PUT", "/settings", json=settings)

    def update_branding(self, branding: dict) -> dict | None:
        """Update branding settings only."""
        return self._request("PUT", "/settings/branding", json=branding)

    def update_currency(self, currency: dict) -> dict | None:
        """Update currency settings only."""
        return self._request("PUT", "/settings/currency", json=currency)

    def update_tax(self, tax: dict) -> dict | None:
        """Update tax settings only."""
        return self._request("PUT", "/settings/tax", json=tax)

    def update_theme(self, theme: dict) -> dict | None:
        """Update theme settings only."""
        return self._request("PUT", "/settings/theme", json=theme)

    def get_currencies(self) -> list[dict]:
        """Get list of available currencies."""
        data = self._request("GET", "/settings/currencies")
        return data if isinstance(data, list) else []

    def get_timezones(self) -> list[dict]:
        """Get list of available timezones."""
        data = self._request("GET", "/settings/timezones")
        return data if isinstance(data, list) else []

    # ===================
    # Promotions API
    # ===================

    def get_promotions(self, active_only: bool = False) -> list[dict]:
        """Get all promotions."""
        params = {"active_only": active_only}
        data = self._request("GET", "/promotions", params=params)
        if isinstance(data, dict) and "promotions" in data:
            return data["promotions"]
        return data if isinstance(data, list) else []

    def get_promotion(self, promotion_id: str) -> dict | None:
        """Get a single promotion by ID."""
        return self._request("GET", f"/promotions/{promotion_id}")

    def create_promotion(self, promotion: dict) -> dict | None:
        """Create a new promotion."""
        return self._request("POST", "/promotions", json=promotion)

    def update_promotion(self, promotion_id: str, promotion: dict) -> dict | None:
        """Update an existing promotion."""
        return self._request("PUT", f"/promotions/{promotion_id}", json=promotion)

    def delete_promotion(self, promotion_id: str) -> dict | None:
        """Delete a promotion."""
        return self._request("DELETE", f"/promotions/{promotion_id}")

    def activate_promotion(self, promotion_id: str) -> dict | None:
        """Activate a promotion."""
        return self._request("POST", f"/promotions/{promotion_id}/activate")

    def deactivate_promotion(self, promotion_id: str) -> dict | None:
        """Deactivate a promotion."""
        return self._request("POST", f"/promotions/{promotion_id}/deactivate")


api_service = ApiService()
