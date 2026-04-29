#!/usr/bin/env python
"""Patch the generated Postman full collection to add an E2E setup folder.

Why this exists
--------------
`backend/postman-full-collection.json` is generated from OpenAPI and includes *all* endpoints,
but many endpoints require IDs (product_id, sale_id, etc.) that are not known ahead of time.

This script creates a runner-friendly E2E suite:
- Keeps the generated requests for broad endpoint coverage.
- Inserts a small "Setup (Auto IDs)" folder that creates core entities and stores their IDs
  into environment variables, so dependent requests can run without manual copy/paste.

Usage (from backend/):
  py -m poetry run python scripts/patch_postman_collection_add_setup.py

Inputs/Outputs:
- Reads:  postman-full-collection.json
- Writes: postman-e2e-collection.json
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
FULL_COLLECTION = BACKEND_ROOT / "postman-full-collection.json"
E2E_COLLECTION = BACKEND_ROOT / "postman-e2e-collection.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _postman_script(lines: list[str]) -> dict[str, Any]:
    return {"type": "text/javascript", "exec": lines}


def _event(listen: str, lines: list[str]) -> dict[str, Any]:
    return {"listen": listen, "script": _postman_script(lines)}


def _url(raw: str) -> dict[str, Any]:
    # Use raw + host/path so Postman renders nicely.
    return {
        "raw": raw,
        "host": ["{{baseUrl}}"],
        "path": [p for p in raw.replace("{{baseUrl}}", "").lstrip("/").split("/") if p],
    }


def _json_request(name: str, method: str, path: str, body: dict[str, Any] | None, *, save_var: str | None = None,
                  save_expr: str | None = None, extra_tests: list[str] | None = None) -> dict[str, Any]:
    headers = [
        {"key": "Content-Type", "value": "application/json"},
        {"key": "Authorization", "value": "Bearer {{accessToken}}"},
    ]

    events: list[dict[str, Any]] = [
        _event(
            "prerequest",
            [
                "if (!pm.environment.get('accessToken')) {",
                "  pm.collectionVariables.set('postLoginNext', pm.info.requestName);",
                "  postman.setNextRequest('00 Auth / Login');",
                "}",
            ],
        )
    ]

    test_lines: list[str] = [
        "pm.test('Status is 2xx', function () {",
        "  pm.expect(pm.response.code).to.be.within(200, 299);",
        "});",
    ]

    if save_var and save_expr:
        test_lines += [
            "let json = {};",
            "try { json = pm.response.json(); } catch (e) { json = {}; }",
            f"const value = {save_expr};",
            "if (value) {",
            f"  pm.environment.set('{save_var}', value);",
            "}",
            f"pm.test('{save_var} set', function () {{",
            f"  pm.expect(pm.environment.get('{save_var}')).to.be.ok;",
            "});",
        ]

    if extra_tests:
        test_lines += extra_tests

    events.append(_event("test", test_lines))

    req: dict[str, Any] = {
        "method": method,
        "header": headers,
        "url": _url(f"{{{{baseUrl}}}}{path}"),
    }
    if body is not None:
        req["body"] = {"mode": "raw", "raw": json.dumps(body, indent=2)}

    return {
        "name": name,
        "event": events,
        "request": req,
    }


def _setup_folder() -> dict[str, Any]:
    # NOTE: These payloads are based on backend/app/api/schemas/*
    # and are intended to be low-risk to run repeatedly.
    return {
        "name": "01 Setup (Auto IDs)",
        "item": [
            _json_request(
                "Setup / Create Category (sets category_id)",
                "POST",
                "/api/v1/categories",
                {
                    "name": "PM Category {{$timestamp}}",
                    "description": "Created by Postman E2E suite",
                },
                save_var="category_id",
                save_expr="json.id",
            ),
            _json_request(
                "Setup / Create Product (sets product_id)",
                "POST",
                "/api/v1/products",
                {
                    "name": "PM Product {{$timestamp}}",
                    "sku": "PM-SKU-{{$timestamp}}",
                    "retail_price": 10.00,
                    "purchase_price": 5.00,
                    "currency": "USD",
                    "category_id": "{{category_id}}",
                },
                save_var="product_id",
                save_expr="json.id",
            ),
            _json_request(
                "Setup / Create Customer (sets customer_id)",
                "POST",
                "/api/v1/customers",
                {
                    "first_name": "Postman",
                    "last_name": "Customer",
                    "email": "pm.customer.{{$timestamp}}@example.com",
                    "phone": "5551234567",
                },
                save_var="customer_id",
                save_expr="json.id",
            ),
            _json_request(
                "Setup / Create Supplier (sets supplier_id)",
                "POST",
                "/api/v1/suppliers",
                {
                    "name": "PM Supplier {{$timestamp}}",
                    "contact_email": "pm.supplier.{{$timestamp}}@example.com",
                    "contact_phone": "5550000000",
                },
                save_var="supplier_id",
                save_expr="json.id",
            ),
            _json_request(
                "Setup / Create Employee (sets employee_id)",
                "POST",
                "/api/v1/employees",
                {
                    "first_name": "Postman",
                    "last_name": "Employee",
                    "email": "pm.employee.{{$timestamp}}@example.com",
                    "phone": "5551112222",
                    "position": "Cashier",
                    "hire_date": "2025-01-01",
                    "base_salary": 0,
                    "create_user_account": False,
                },
                save_var="employee_id",
                save_expr="json.id",
            ),
            _json_request(
                "Setup / Create Sale (sets sale_id + sale_item_id)",
                "POST",
                "/api/v1/sales",
                {
                    "currency": "USD",
                    "customer_id": "{{customer_id}}",
                    "lines": [
                        {
                            "product_id": "{{product_id}}",
                            "quantity": 1,
                            "unit_price": 10.00,
                        }
                    ],
                    "payments": [
                        {
                            "payment_method": "cash",
                            "amount": 10.00,
                        }
                    ],
                },
                save_var="sale_id",
                save_expr="json.sale && json.sale.id",
                extra_tests=[
                    "let json = {};",
                    "try { json = pm.response.json(); } catch (e) { json = {}; }",
                    "const firstItem = json.sale && json.sale.items && json.sale.items.length ? json.sale.items[0] : null;",
                    "if (firstItem && firstItem.id) { pm.environment.set('sale_item_id', firstItem.id); }",
                    "pm.test('sale_item_id set', function () {",
                    "  pm.expect(pm.environment.get('sale_item_id')).to.be.ok;",
                    "});",
                ],
            ),
            _json_request(
                "Setup / Create Return (sets return_id)",
                "POST",
                "/api/v1/returns",
                {
                    "sale_id": "{{sale_id}}",
                    "lines": [
                        {
                            "sale_item_id": "{{sale_item_id}}",
                            "quantity": 1,
                        }
                    ],
                },
                save_var="return_id",
                save_expr="json.return && json.return.id",
            ),
        ],
    }


def main() -> int:
    if not FULL_COLLECTION.exists():
        print(f"Missing input collection: {FULL_COLLECTION}", file=sys.stderr)
        return 2

    data = json.loads(FULL_COLLECTION.read_text(encoding="utf-8"))
    items = data.get("item")
    if not isinstance(items, list):
        print("Invalid collection: missing 'item' array", file=sys.stderr)
        return 2

    # Find the "00 Auth" folder to insert setup after it.
    auth_index = None
    for i, it in enumerate(items):
        if isinstance(it, dict) and str(it.get("name", "")).strip() == "00 Auth":
            auth_index = i
            break

    setup = _setup_folder()
    if auth_index is None:
        # Conservative fallback: prepend if auth folder not found.
        items.insert(0, setup)
    else:
        items.insert(auth_index + 1, setup)

    # Update metadata (keep schema version)
    info = data.get("info") or {}
    info["name"] = "Retail POS Backend (E2E Suite)"
    info["_postman_id"] = f"retail-pos-backend-e2e-{uuid.uuid4()}"
    data["info"] = info

    # Add/refresh top-level variables (non-breaking)
    data.setdefault("variable", [])
    if isinstance(data["variable"], list):
        # Ensure postLoginNext variable exists for redirect behavior.
        has_post_login_next = any(
            isinstance(v, dict) and v.get("key") == "postLoginNext" for v in data["variable"]
        )
        if not has_post_login_next:
            data["variable"].append({"key": "postLoginNext", "value": ""})

    E2E_COLLECTION.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote: {E2E_COLLECTION} ({_now_iso()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
