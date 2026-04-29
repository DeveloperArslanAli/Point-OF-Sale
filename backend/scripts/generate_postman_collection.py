"""Generate a Postman collection from the FastAPI OpenAPI schema.

Usage (from backend/):
  poetry run python scripts/generate_postman_collection.py \
    --out postman-full-collection.json \
    --name "Retail POS Backend (Full)"

This intentionally generates a *broad smoke suite*:
- Includes every OpenAPI path+method.
- Adds basic tests (status code is one of documented responses; JSON parse when applicable).
- Adds placeholder bodies for JSON request payloads using OpenAPI component schemas.

The generated collection uses environment variables:
- {{baseUrl}}            e.g. http://localhost:8000
- {{adminEmail}}         e.g. admin@retailpos.com
- {{adminPassword}}      e.g. AdminPass123!
- {{accessToken}}        set automatically by the login request

It also uses placeholder variables for path params (e.g. {{product_id}}).
Populate them in your environment or set them via earlier requests.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Ensure `backend/` is importable when running from repo root or via absolute path.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


DEFAULT_COLLECTION_NAME = "Retail POS Backend (Full)"
POSTMAN_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _deep_get(d: dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


@dataclass(frozen=True)
class Operation:
    path: str
    method: str
    summary: str
    tags: list[str]
    operation_id: str | None
    security: list[dict[str, list[str]]] | None
    responses: dict[str, Any]
    parameters: list[dict[str, Any]]
    request_body: dict[str, Any] | None


def _load_openapi() -> dict[str, Any]:
    # Importing the FastAPI app can execute settings validation; keep it direct.
    from app.api.main import app  # type: ignore

    return app.openapi()


def _collect_operations(openapi: dict[str, Any]) -> list[Operation]:
    ops: list[Operation] = []
    paths = openapi.get("paths", {})
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "options", "head"):
            if method not in path_item:
                continue
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            summary = op.get("summary") or op.get("operationId") or f"{method.upper()} {path}"
            tags = list(op.get("tags") or [])
            operation_id = op.get("operationId")
            security = op.get("security")
            responses = op.get("responses") or {}
            # parameters can live both at path and op level
            parameters: list[dict[str, Any]] = []
            for p in (path_item.get("parameters") or []):
                if isinstance(p, dict):
                    parameters.append(p)
            for p in (op.get("parameters") or []):
                if isinstance(p, dict):
                    parameters.append(p)
            request_body = op.get("requestBody")

            ops.append(
                Operation(
                    path=str(path),
                    method=method.upper(),
                    summary=str(summary),
                    tags=tags,
                    operation_id=operation_id,
                    security=security,
                    responses=responses,
                    parameters=parameters,
                    request_body=request_body if isinstance(request_body, dict) else None,
                )
            )

    # stable ordering: tag then path then method
    def _key(o: Operation) -> tuple[str, str, str]:
        tag = o.tags[0] if o.tags else "(untagged)"
        return (tag.lower(), o.path, o.method)

    return sorted(ops, key=_key)


def _resolve_ref(openapi: dict[str, Any], ref: str) -> dict[str, Any] | None:
    # Only supports local components refs.
    if not ref.startswith("#/" ):
        return None
    parts = [p for p in ref[2:].split("/") if p]
    cur: Any = openapi
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur if isinstance(cur, dict) else None


def _example_for_schema(openapi: dict[str, Any], schema: dict[str, Any], *, depth: int = 0) -> Any:
    if depth > 4:
        return None

    if "$ref" in schema:
        ref_schema = _resolve_ref(openapi, schema["$ref"])
        if ref_schema is None:
            return None
        return _example_for_schema(openapi, ref_schema, depth=depth + 1)

    if "example" in schema:
        return schema["example"]

    if "default" in schema:
        return schema["default"]

    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]

    if "anyOf" in schema and isinstance(schema["anyOf"], list) and schema["anyOf"]:
        return _example_for_schema(openapi, schema["anyOf"][0], depth=depth + 1)

    if "oneOf" in schema and isinstance(schema["oneOf"], list) and schema["oneOf"]:
        return _example_for_schema(openapi, schema["oneOf"][0], depth=depth + 1)

    t = schema.get("type")
    fmt = schema.get("format")

    if t == "string":
        if fmt == "email":
            return "test@example.com"
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        if fmt == "date-time":
            return "2025-01-01T00:00:00Z"
        if fmt == "date":
            return "2025-01-01"
        if fmt == "uri":
            return "https://example.com"
        return "string"

    if t == "integer":
        return 1

    if t == "number":
        return 1.0

    if t == "boolean":
        return True

    if t == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            return [_example_for_schema(openapi, items, depth=depth + 1)]
        return []

    if t == "object" or "properties" in schema:
        props = schema.get("properties")
        if not isinstance(props, dict):
            return {}
        required = schema.get("required")
        required_set = set(required) if isinstance(required, list) else set()
        # include required fields if known, otherwise include a small subset
        keys = list(props.keys())
        chosen: list[str] = [k for k in keys if k in required_set]
        if not chosen:
            chosen = keys[:6]
        obj: dict[str, Any] = {}
        for k in chosen:
            v = props.get(k)
            if isinstance(v, dict):
                obj[k] = _example_for_schema(openapi, v, depth=depth + 1)
        return obj

    return None


def _guess_json_body(openapi: dict[str, Any], request_body: dict[str, Any] | None) -> str | None:
    if not request_body:
        return None
    content = request_body.get("content")
    if not isinstance(content, dict):
        return None
    app_json = content.get("application/json")
    if not isinstance(app_json, dict):
        # some endpoints might use multipart/form-data
        return None

    schema = app_json.get("schema")
    if not isinstance(schema, dict):
        return None

    example = _example_for_schema(openapi, schema)
    if example is None:
        return None
    return json.dumps(example, indent=2, ensure_ascii=False)


def _postman_url(raw: str) -> dict[str, Any]:
    # Postman URL object supports raw/host/path. We keep raw to preserve {{baseUrl}}.
    # raw already includes baseUrl.
    return {
        "raw": raw,
        "host": ["{{baseUrl}}"],
        "path": [p for p in raw.replace("{{baseUrl}}", "").lstrip("/").split("/") if p],
    }


def _expected_statuses(responses: dict[str, Any]) -> list[int]:
    statuses: list[int] = []
    for code in responses.keys():
        if isinstance(code, str) and code.isdigit():
            statuses.append(int(code))
    # default fallback
    if not statuses:
        return [200, 201, 202, 204]
    return sorted(set(statuses))


def _requires_bearer(op: Operation, openapi: dict[str, Any]) -> bool:
    # FastAPI OpenAPI uses "security" at op-level; if absent, may still exist globally.
    security = op.security
    if security is None:
        security = openapi.get("security")
    if not security:
        return False
    if not isinstance(security, list):
        return False

    bearer_schemes: set[str] = set()
    for name, scheme in (openapi.get("components", {}).get("securitySchemes", {}) or {}).items():
        if not isinstance(scheme, dict):
            continue
        if scheme.get("type") == "http" and scheme.get("scheme") == "bearer":
            bearer_schemes.add(str(name))

    # if any security requirement references a bearer scheme, mark it as needing auth
    for req in security:
        if not isinstance(req, dict):
            continue
        for scheme_name in req.keys():
            if scheme_name in bearer_schemes:
                return True
    return False


def _make_test_script(expected_statuses: list[int]) -> list[str]:
    statuses_js = json.dumps(expected_statuses)
    return [
        "pm.test('Status is expected', function () {",
        f"  const expected = {statuses_js};",
        "  pm.expect(expected).to.include(pm.response.code);",
        "});",
        "",
        "pm.test('Response time < 5s', function () {",
        "  pm.expect(pm.response.responseTime).to.be.below(5000);",
        "});",
        "",
        "// If JSON, ensure it parses",
        "pm.test('Valid JSON when applicable', function () {",
        "  const ct = (pm.response.headers.get('Content-Type') || '').toLowerCase();",
        "  if (ct.includes('application/json')) {",
        "    pm.response.json();",
        "  }",
        "});",
    ]


def _make_auth_gate_prerequest(op_name: str) -> list[str]:
    # Only used for endpoints that require auth.
    # In collection runner, redirects to login then resumes.
    return [
        "if (!pm.environment.get('accessToken')) {",
        f"  pm.collectionVariables.set('postLoginNext', '{op_name}');",
        "  postman.setNextRequest('00 Auth / Login');",
        "}",
    ]


def _make_login_request(api_prefix: str) -> dict[str, Any]:
    return {
        "name": "00 Auth / Login",
        "event": [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "pm.test('Login returned 200', function () {",
                        "  pm.response.to.have.status(200);",
                        "});",
                        "const json = pm.response.json();",
                        "if (json && json.access_token) {",
                        "  pm.environment.set('accessToken', json.access_token);",
                        "}",
                        "pm.test('accessToken set', function () {",
                        "  pm.expect(pm.environment.get('accessToken')).to.be.ok;",
                        "});",
                        "const next = pm.collectionVariables.get('postLoginNext');",
                        "if (next) {",
                        "  pm.collectionVariables.unset('postLoginNext');",
                        "  postman.setNextRequest(next);",
                        "}",
                    ],
                },
            }
        ],
        "request": {
            "method": "POST",
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "url": _postman_url(f"{{{{baseUrl}}}}{api_prefix}/auth/login"),
            "body": {
                "mode": "raw",
                "raw": json.dumps(
                    {"email": "{{adminEmail}}", "password": "{{adminPassword}}"},
                    indent=2,
                    ensure_ascii=False,
                ),
            },
        },
    }


def _folder_name(op: Operation) -> str:
    if op.tags:
        return op.tags[0]
    # fallback: first path segment
    parts = [p for p in op.path.split("/") if p and not p.startswith("{")]
    return parts[0] if parts else "Misc"


def _request_name(op: Operation) -> str:
    # Postman runner setNextRequest uses exact name.
    return f"{_folder_name(op)} / {op.method} {op.path}"


def _make_request_item(openapi: dict[str, Any], op: Operation, api_prefix: str) -> dict[str, Any]:
    raw_url = f"{{{{baseUrl}}}}{api_prefix}{op.path}"
    expected = _expected_statuses(op.responses)
    body_raw = _guess_json_body(openapi, op.request_body)

    events: list[dict[str, Any]] = []

    if _requires_bearer(op, openapi) and not op.path.startswith("/auth/"):
        events.append(
            {
                "listen": "prerequest",
                "script": {"type": "text/javascript", "exec": _make_auth_gate_prerequest(_request_name(op))},
            }
        )

    events.append({"listen": "test", "script": {"type": "text/javascript", "exec": _make_test_script(expected)}})

    headers: list[dict[str, str]] = []
    if _requires_bearer(op, openapi) and not op.path.startswith("/auth/"):
        headers.append({"key": "Authorization", "value": "Bearer {{accessToken}}"})

    if body_raw is not None:
        headers.append({"key": "Content-Type", "value": "application/json"})

    req: dict[str, Any] = {
        "method": op.method,
        "header": headers,
        "url": _postman_url(raw_url),
    }

    if body_raw is not None:
        req["body"] = {"mode": "raw", "raw": body_raw}

    return {"name": _request_name(op), "event": events, "request": req}


def _build_collection(openapi: dict[str, Any], *, name: str) -> dict[str, Any]:
    api_prefix = str(openapi.get("servers", [{}])[0].get("url", ""))
    # Your app uses settings.API_V1_PREFIX (likely "/api/v1"). OpenAPI servers may be absent.
    # So we infer from the auth login in the existing smoke collection.
    if not api_prefix or api_prefix == "/":
        api_prefix = "/api/v1"

    ops = _collect_operations(openapi)

    folders: dict[str, list[dict[str, Any]]] = {}
    for op in ops:
        folder = _folder_name(op)
        folders.setdefault(folder, []).append(_make_request_item(openapi, op, api_prefix))

    # Ensure auth folder exists and is first
    items: list[dict[str, Any]] = []
    items.append({"name": "00 Auth", "item": [_make_login_request(api_prefix)]})

    for folder_name in sorted(folders.keys(), key=lambda s: s.lower()):
        items.append({"name": folder_name, "item": folders[folder_name]})

    return {
        "info": {
            "_postman_id": f"{_slug(name)}-{_slug(_now_iso())}",
            "name": name,
            "schema": POSTMAN_SCHEMA,
        },
        "item": items,
        "variable": [
            {"key": "postLoginNext", "value": ""},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="postman-full-collection.json")
    parser.add_argument("--name", default=DEFAULT_COLLECTION_NAME)
    args = parser.parse_args()

    openapi = _load_openapi()
    collection = _build_collection(openapi, name=args.name)

    out_path = Path(args.out)
    out_path.write_text(json.dumps(collection, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote Postman collection: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
