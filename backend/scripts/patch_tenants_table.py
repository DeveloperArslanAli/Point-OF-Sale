"""Ensure tenants table matches current model (slug, is_active columns).

Adds columns if missing and backfills slug from name.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.infrastructure.db.session import engine


async def main() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS slug varchar(100);"))
        await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT TRUE;"))
        await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS subscription_plan_id varchar(26);"))
        await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS subscription_status varchar(50) DEFAULT 'active';"))
        await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS billing_cycle varchar(20) DEFAULT 'monthly';"))
        await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS stripe_customer_id varchar(255);"))
        await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS stripe_subscription_id varchar(255);"))
        await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS trial_ends_at timestamptz;"))
        await conn.execute(text("UPDATE tenants SET slug = lower(replace(name,' ', '-')) WHERE slug IS NULL;"))
    print("tenants table patched (slug, is_active)")


if __name__ == "__main__":
    asyncio.run(main())