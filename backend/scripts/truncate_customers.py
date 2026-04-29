import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.settings import get_settings


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE customers RESTART IDENTITY CASCADE"))
    await engine.dispose()
    print("customers truncated")


if __name__ == "__main__":
    asyncio.run(main())
