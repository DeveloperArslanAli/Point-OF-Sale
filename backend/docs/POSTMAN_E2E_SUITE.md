# Postman E2E Suite (Runner-friendly)

This backend ships with a **full generated collection** (broad coverage) and an **E2E suite** (adds setup requests that auto-fill IDs).

## Files
- Collection: `backend/postman-e2e-collection.json`
- Environment: `backend/postman-env.local.e2e.json`

## What the E2E suite does
- Runs `00 Auth / Login` first to set `{{accessToken}}`.
- Runs `01 Setup (Auto IDs)` to create:
  - Category → sets `{{category_id}}`
  - Product → sets `{{product_id}}`
  - Customer → sets `{{customer_id}}`
  - Supplier → sets `{{supplier_id}}`
  - Employee → sets `{{employee_id}}`
  - Sale → sets `{{sale_id}}` and `{{sale_item_id}}`
  - Return → sets `{{return_id}}`

After that, the remaining requests from the generated full suite run using those variables where applicable.

## Import into Postman
1. Import the environment: `backend/postman-env.local.e2e.json`
2. Import the collection: `backend/postman-e2e-collection.json`
3. Select the environment **Local (E2E Suite)**.

## Run it
- Start the backend (choose one):
  - Docker dev stack: `./scripts/dev_env_up.ps1`
  - Local: `cd backend; py -m poetry run uvicorn app.api.main:app --reload --port 8000`
- In Postman: Collection Runner → run the whole collection.

## Regenerate
If `backend/postman-full-collection.json` changes, re-run:

```powershell
cd backend
py -m poetry run python scripts/patch_postman_collection_add_setup.py
```
