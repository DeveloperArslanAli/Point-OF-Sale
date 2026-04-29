import asyncio
import os
from typing import Iterable

import asyncpg

REQUIRED_COLUMNS = {
    "products": ["tenant_id"],
    "categories": ["tenant_id"],
    "customers": ["tenant_id", "email_hash"],
    "suppliers": ["tenant_id"],
    "employees": ["tenant_id"],
}


def _normalize_dsn(raw: str | None) -> str:
    if not raw:
        raise RuntimeError("DATABASE_URL is not set")
    # Alembic/app use asyncpg driver; asyncpg.connect expects plain pg dsn
    return raw.replace("+asyncpg", "")


ASYNC_QUERY = (
    "select table_name, column_name "
    "from information_schema.columns "
    "where table_name = any($1::text[]) and column_name = any($2::text[]) "
    "order by table_name, column_name"
)


async def main() -> None:
    dsn = _normalize_dsn(os.getenv("DATABASE_URL"))
    tables: list[str] = sorted(REQUIRED_COLUMNS.keys())
    columns: list[str] = sorted({c for cols in REQUIRED_COLUMNS.values() for c in cols})

    conn = await asyncpg.connect(dsn)
    rows = await conn.fetch(ASYNC_QUERY, tables, columns)
    await conn.close()

    present: dict[str, set[str]] = {t: set() for t in tables}
    for row in rows:
        present[row["table_name"]].add(row["column_name"])

    missing: list[str] = []
    for table, needed_cols in REQUIRED_COLUMNS.items():
        for col in needed_cols:
            if col not in present.get(table, set()):
                missing.append(f"{table}.{col}")

    if missing:
        print("MISSING:")
        for item in missing:
            print(f" - {item}")
        raise SystemExit(1)

    print("All required columns present:")
    for table in tables:
        cols = ", ".join(sorted(present[table]))
        print(f" - {table}: {cols}")


if __name__ == "__main__":
    asyncio.run(main())
