import asyncio
import logging

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from src.shared.db import engine  # assumes your engine is defined here
from src.file_service.models import Base, Tenant  # your ORM models
from datetime import datetime

# Optional: Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create sessionmaker (if not already in db.py)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def run():
    print("🔁 Dropping and creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created successfully")

    # Insert a sample tenant
    print("➕ Inserting a test tenant...")
    async with AsyncSessionLocal() as session:
        tenant = Tenant(
            tenant_id="ABC123",
            tenant_code="ABC123",
            configuration={
                "max_size": 1024,
                "allowed_extensions": ["pdf", "docx", "txt"],
                "media_types": ["application/pdf", "application/msword", "text/plain"],
                "max_zip_depth": 3,
            },
        )
        session.add(tenant)
        await session.commit()
    print("✅ Tenant inserted")

    # Fetch and print the inserted tenant
    # async with AsyncSessionLocal() as session:
    #     result = await session.get(Tenant, 1)
    #     print("🔎 Inserted Tenant:", result)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
