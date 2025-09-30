import asyncio
import logging

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from src.shared.db import engine
from src.file_service.models import Base, Tenant
from datetime import datetime
from src.shared.utils import setup_logger

logger = setup_logger()

# Create sessionmaker (if not already in db.py)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def run():
    logger.debug("Dropping and creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.debug("Tables created successfully")

    # Insert a sample tenant
    logger.debug("Inserting a test tenant...")
    async with AsyncSessionLocal() as session:
        tenant = Tenant(
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
    logger.debug("Tenant inserted")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
