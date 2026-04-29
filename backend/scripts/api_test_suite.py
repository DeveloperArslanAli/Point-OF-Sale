#!/usr/bin/env python
"""
Comprehensive API Test Suite for Retail POS
Tests all endpoints and reports pass/fail status
"""

import asyncio
import httpx
import sys
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

BASE_URL = "http://127.0.0.1:8005"

@dataclass
class TestResult:
    name: str
    endpoint: str
    method: str
    status: str  # PASS, FAIL, EXPECTED
    code: int
    detail: str = ""

results: list[TestResult] = []
token: Optional[str] = None
admin_token: Optional[str] = None


async def test_endpoint(
    client: httpx.AsyncClient,
    name: str,
    method: str,
    endpoint: str,
    body: dict = None,
    headers: dict = None,
    expect_code: int = None,
    auth: bool = False,
) -> TestResult:
    """Test a single endpoint"""
    global token
    
    url = f"{BASE_URL}{endpoint}"
    req_headers = headers or {}
    
    if auth and token:
        req_headers["Authorization"] = f"Bearer {token}"
    
    try:
        if method == "GET":
            resp = await client.get(url, headers=req_headers)
        elif method == "POST":
            resp = await client.post(url, json=body, headers=req_headers)
        elif method == "PATCH":
            resp = await client.patch(url, json=body, headers=req_headers)
        elif method == "PUT":
            resp = await client.put(url, json=body, headers=req_headers)
        elif method == "DELETE":
            resp = await client.delete(url, headers=req_headers)
        else:
            return TestResult(name, endpoint, method, "FAIL", 0, f"Unknown method: {method}")
        
        code = resp.status_code
        
        if expect_code and code == expect_code:
            return TestResult(name, endpoint, method, "EXPECTED", code, f"Got {code} as expected")
        elif 200 <= code < 300:
            return TestResult(name, endpoint, method, "PASS", code)
        elif expect_code:
            return TestResult(name, endpoint, method, "FAIL", code, f"Expected {expect_code}")
        else:
            detail = resp.text[:100] if resp.text else ""
            return TestResult(name, endpoint, method, "FAIL", code, detail)
            
    except httpx.ConnectError:
        return TestResult(name, endpoint, method, "FAIL", 0, "Connection refused - server not running?")
    except Exception as e:
        return TestResult(name, endpoint, method, "FAIL", 0, str(e)[:80])


async def run_tests():
    global token, admin_token, results
    
    print("\n" + "=" * 60)
    print("       RETAIL POS - COMPREHENSIVE API TEST SUITE")
    print("=" * 60)
    print(f"  Base URL: {BASE_URL}")
    print(f"  Started:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # ========== HEALTH & MONITORING ==========
        print("📋 HEALTH & MONITORING")
        print("-" * 40)
        
        r = await test_endpoint(client, "Health Check", "GET", "/health")
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Metrics", "GET", "/metrics")
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "OpenAPI Spec", "GET", "/openapi.json")
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "API Docs", "GET", "/docs")
        results.append(r)
        print_result(r)
        
        # ========== AUTHENTICATION ==========
        print("\n🔐 AUTHENTICATION")
        print("-" * 40)
        
        # Login with admin
        r = await test_endpoint(
            client, "Admin Login", "POST", "/api/v1/auth/login",
            body={"email": "admin@retailpos.com", "password": "AdminPass123!"}
        )
        results.append(r)
        print_result(r)
        
        # Try to get token
        try:
            resp = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": "admin@retailpos.com", "password": "AdminPass123!"}
            )
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("access_token")
                admin_token = token
                print(f"   ✓ Token acquired: {token[:20]}..." if token else "   ⚠ No token in response")
        except Exception as e:
            print(f"   ⚠ Token error: {e}")
        
        r = await test_endpoint(client, "Get Current User", "GET", "/api/v1/auth/me", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "List Users (Admin)", "GET", "/api/v1/auth/users", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Admin Actions Log", "GET", "/api/v1/auth/admin-actions", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(
            client, "Login - Invalid Creds", "POST", "/api/v1/auth/login",
            body={"email": "wrong@test.com", "password": "wrong"},
            expect_code=401
        )
        results.append(r)
        print_result(r)
        
        # ========== CATEGORIES ==========
        print("\n📁 CATEGORIES")
        print("-" * 40)
        
        r = await test_endpoint(client, "List Categories", "GET", "/api/v1/categories", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(
            client, "Create Category", "POST", "/api/v1/categories",
            body={"name": f"Test Category {datetime.now().timestamp()}", "description": "API Test"},
            auth=True
        )
        results.append(r)
        print_result(r)
        
        # ========== PRODUCTS ==========
        print("\n📦 PRODUCTS")
        print("-" * 40)
        
        r = await test_endpoint(client, "List Products", "GET", "/api/v1/products", auth=True)
        results.append(r)
        print_result(r)
        
        # Get a category ID first
        cat_id = None
        try:
            resp = await client.get(f"{BASE_URL}/api/v1/categories", headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 200:
                cats = resp.json()
                if cats and len(cats) > 0:
                    cat_id = cats[0].get("id")
        except:
            pass
        
        if cat_id:
            r = await test_endpoint(
                client, "Create Product", "POST", "/api/v1/products",
                body={
                    "sku": f"TEST-{int(datetime.now().timestamp())}",
                    "name": "API Test Product",
                    "price": "19.99",
                    "category_id": cat_id,
                    "stock_quantity": 100
                },
                auth=True
            )
            results.append(r)
            print_result(r)
        
        r = await test_endpoint(client, "Product Import Jobs", "GET", "/api/v1/products/import", auth=True)
        results.append(r)
        print_result(r)
        
        # ========== INVENTORY INTELLIGENCE ==========
        print("\n📊 INVENTORY INTELLIGENCE")
        print("-" * 40)
        
        r = await test_endpoint(client, "Intelligence Dashboard", "GET", "/api/v1/inventory/intelligence", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "ABC Analysis", "GET", "/api/v1/inventory/intelligence/abc", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Forecast", "GET", "/api/v1/inventory/intelligence/forecast", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Advanced Forecast", "GET", "/api/v1/inventory/intelligence/forecast/advanced", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Vendor Performance", "GET", "/api/v1/inventory/intelligence/vendors", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "PO Suggestions", "GET", "/api/v1/inventory/intelligence/po-suggestions", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "PO Drafts", "GET", "/api/v1/inventory/intelligence/po-drafts", auth=True)
        results.append(r)
        print_result(r)
        
        # ========== SUPPLIERS ==========
        print("\n🏭 SUPPLIERS")
        print("-" * 40)
        
        r = await test_endpoint(client, "List Suppliers", "GET", "/api/v1/suppliers", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(
            client, "Create Supplier", "POST", "/api/v1/suppliers",
            body={
                "name": f"Test Supplier {int(datetime.now().timestamp())}",
                "email": "supplier@test.com",
                "phone": "555-1234"
            },
            auth=True
        )
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Supplier Ranking Weights", "GET", "/api/v1/supplier-ranking-weights", auth=True)
        results.append(r)
        print_result(r)
        
        # ========== CUSTOMERS ==========
        print("\n👥 CUSTOMERS")
        print("-" * 40)
        
        r = await test_endpoint(client, "List Customers", "GET", "/api/v1/customers", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(
            client, "Create Customer", "POST", "/api/v1/customers",
            body={
                "first_name": "Test",
                "last_name": "Customer",
                "email": f"test{int(datetime.now().timestamp())}@example.com",
                "phone": "555-0000"
            },
            auth=True
        )
        results.append(r)
        print_result(r)
        
        # ========== SALES ==========
        print("\n💰 SALES")
        print("-" * 40)
        
        r = await test_endpoint(client, "List Sales", "GET", "/api/v1/sales", auth=True)
        results.append(r)
        print_result(r)
        
        # ========== RETURNS ==========
        print("\n↩️ RETURNS")
        print("-" * 40)
        
        r = await test_endpoint(client, "List Returns", "GET", "/api/v1/returns", auth=True)
        results.append(r)
        print_result(r)
        
        # ========== PURCHASES ==========
        print("\n🛒 PURCHASES")
        print("-" * 40)
        
        r = await test_endpoint(client, "List Purchases", "GET", "/api/v1/purchases", auth=True)
        results.append(r)
        print_result(r)
        
        # ========== EMPLOYEES ==========
        print("\n👔 EMPLOYEES")
        print("-" * 40)
        
        r = await test_endpoint(client, "List Employees", "GET", "/api/v1/employees", auth=True)
        results.append(r)
        print_result(r)
        
        # ========== PROMOTIONS ==========
        print("\n🎁 PROMOTIONS")
        print("-" * 40)
        
        r = await test_endpoint(client, "List Promotions", "GET", "/api/v1/promotions", auth=True)
        results.append(r)
        print_result(r)
        
        # ========== RECEIPTS ==========
        print("\n🧾 RECEIPTS")
        print("-" * 40)
        
        r = await test_endpoint(client, "List Receipts", "GET", "/api/v1/receipts", auth=True)
        results.append(r)
        print_result(r)
        
        # ========== REPORTS & ANALYTICS ==========
        print("\n📈 REPORTS & ANALYTICS")
        print("-" * 40)
        
        r = await test_endpoint(client, "Report Definitions", "GET", "/api/v1/reports/definitions", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Sales Trends", "GET", "/api/v1/analytics/sales/trends", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Top Products", "GET", "/api/v1/analytics/sales/top-products", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Inventory Turnover", "GET", "/api/v1/analytics/inventory/turnover", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Employee Performance", "GET", "/api/v1/analytics/employees/performance", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Customer Analytics", "GET", "/api/v1/analytics/customers", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Dashboard Summary", "GET", "/api/v1/analytics/dashboard/summary", auth=True)
        results.append(r)
        print_result(r)
        
        # ========== MONITORING ==========
        print("\n🔍 MONITORING")
        print("-" * 40)
        
        r = await test_endpoint(client, "Health Detailed", "GET", "/api/v1/monitoring/health/detailed", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Celery Workers", "GET", "/api/v1/monitoring/celery/workers", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "Celery Queues", "GET", "/api/v1/monitoring/celery/queues", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "WebSocket Stats", "GET", "/api/v1/ws/stats", auth=True)
        results.append(r)
        print_result(r)
        
        # ========== TENANTS ==========
        print("\n🏢 TENANTS")
        print("-" * 40)
        
        r = await test_endpoint(client, "List Plans", "GET", "/api/v1/tenants/plans", auth=True)
        results.append(r)
        print_result(r)
        
        r = await test_endpoint(client, "List Tenants", "GET", "/api/v1/tenants/", auth=True)
        results.append(r)
        print_result(r)
    
    # ========== SUMMARY ==========
    print("\n" + "=" * 60)
    print("                    TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results if r.status == "PASS")
    expected = sum(1 for r in results if r.status == "EXPECTED")
    failed = sum(1 for r in results if r.status == "FAIL")
    total = len(results)
    
    print(f"\n  ✅ PASSED:   {passed}")
    print(f"  ⚠️  EXPECTED: {expected}")
    print(f"  ❌ FAILED:   {failed}")
    print(f"  📊 TOTAL:    {total}")
    print(f"\n  Success Rate: {((passed + expected) / total * 100):.1f}%")
    
    if failed > 0:
        print("\n" + "-" * 60)
        print("FAILED TESTS - NEEDS FIXING:")
        print("-" * 60)
        for r in results:
            if r.status == "FAIL":
                print(f"\n  ❌ {r.name}")
                print(f"     {r.method} {r.endpoint}")
                print(f"     Code: {r.code}")
                if r.detail:
                    print(f"     Detail: {r.detail}")
    
    print("\n" + "=" * 60)
    print(f"  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")
    
    return failed


def print_result(r: TestResult):
    if r.status == "PASS":
        print(f"  ✅ {r.name} ({r.code})")
    elif r.status == "EXPECTED":
        print(f"  ⚠️  {r.name} ({r.code} as expected)")
    else:
        print(f"  ❌ {r.name} ({r.code}) - {r.detail[:50]}")


if __name__ == "__main__":
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
