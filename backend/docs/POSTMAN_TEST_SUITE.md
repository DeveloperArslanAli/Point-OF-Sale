# Postman Test Suite (Full Backend)

This repo includes a **generated Postman collection** that covers **all FastAPI endpoints** registered in the backend OpenAPI schema.

## Files
- backend/postman-full-collection.json
- backend/postman-env.local.full.json

## Runner-friendly E2E suite (recommended)
If you want a collection that **auto-creates core records and stores IDs** (so the runner can execute more endpoints without manual setup), use:
- backend/postman-e2e-collection.json
- backend/postman-env.local.e2e.json

See: `backend/docs/POSTMAN_E2E_SUITE.md`

## Import into Postman
1. Import the environment: `backend/postman-env.local.full.json`
2. Import the collection: `backend/postman-full-collection.json`
3. Select the environment **Local (Full Suite)**.

## Running the suite
- Run the collection using **Collection Runner**.
- The first request is `00 Auth / Login`.
- Most endpoints require `{{accessToken}}`. If it’s missing, requests will redirect to `00 Auth / Login` (works in the Runner).

## Required setup
- Start the API (local or docker compose): baseUrl defaults to `http://localhost:8000`
- Ensure the seeded admin exists (see backend/README.md):
  - `admin@retailpos.com`
  - `AdminPass123!`

## Notes on IDs / path parameters
Many endpoints require IDs like `product_id`, `customer_id`, etc.

- The generated requests use `{{param_name}}` variables for all path parameters.
- Populate those variables in the environment (e.g. set `product_id` to a real product id) or run create endpoints first and copy IDs.

## Regenerating the collection
The collection is generated from `app.api.main:app` OpenAPI:

```powershell
E:/Projects/retail/Pos-phython/backend/.venv/Scripts/python.exe backend/scripts/generate_postman_collection.py `
  --out backend/postman-full-collection.json `
  --name "Retail POS Backend (Full)"
```

To regenerate the E2E suite (inserts the Setup folder into the generated full collection):

```powershell
E:/Projects/retail/Pos-phython/backend/.venv/Scripts/python.exe backend/scripts/patch_postman_collection_add_setup.py
```
