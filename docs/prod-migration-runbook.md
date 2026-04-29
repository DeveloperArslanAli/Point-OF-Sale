# Production Migration Runbook – product_supplier_links repair

## Preconditions
- Confirm production `DATABASE_URL` (Postgres with asyncpg DSN) is available.
- Take a production DB backup/snapshot and verify restore steps are documented.
- Ensure you can run commands from `backend/` with Poetry environment available.

## Execution (choose platform)
### PowerShell (Windows jump box)
```
$env:DATABASE_URL="postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME"
Set-Location E:/Projects/retail/Pos-phython/backend
py -m poetry run alembic upgrade head
```

### Linux/macOS
```
export DATABASE_URL="postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME"
cd /path/to/Pos-phython/backend
py -m poetry run alembic upgrade head
```

## Post-migration validation
```
py -m poetry run python - <<'PY'
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        ver = await conn.execute(text("select version_num from alembic_version"))
        print("alembic_version:", ver.fetchall())
        cols = await conn.execute(text("""
            select column_name from information_schema.columns
            where table_name='product_supplier_links'
            order by ordinal_position
        """))
        print("product_supplier_links columns:", [c[0] for c in cols.fetchall()])
    await engine.dispose()
asyncio.run(main())
PY
```
Expected: `alembic_version` shows `r2s3t4u5v6w7`; columns include `tenant_id`, `product_id`, `supplier_id`, `unit_cost`, `is_preferred`, `priority`, `is_active`, timestamps.

### Endpoint check
- Hit `/api/v1/inventory/intelligence/po-drafts` with a valid admin token; expect HTTP 200 (no 500s).

## Rollback
- Restore the DB from the snapshot/backup taken before this run.
- If code deploy changed, redeploy the previous application image/version.

## Notes
- Migration `r2s3t4u5v6w7` is idempotent and will auto-heal a missing `product_supplier_links` table and indexes.
- Keep this migration in the repo so future deploys do not regress if a DB was stamped without running `j4k5l6m7n8o9`.
