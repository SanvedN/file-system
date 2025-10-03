import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from shared.db import engine, Base
from file_service.models import Tenant, File
from datetime import datetime
from shared.utils import setup_logger

logger = setup_logger()

# Create sessionmaker (if not already in db.py)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def run():
    logger.debug("Dropping and creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.debug("Tables created successfully")

    id = uuid.uuid4()

    # Insert a sample tenant
    logger.debug("Inserting a test tenant...")
    async with AsyncSessionLocal() as session:
        tenant = Tenant(tenant_id=id, tenant_code="ABC123")
        session.add(tenant)
        await session.commit()
    logger.debug("Tenant inserted")

    # Insert a sample tenant
    logger.debug("Inserting a test file row...")
    async with AsyncSessionLocal() as session:
        file = File(
            tenant_id=id,  # Use an actual Tenant ID from DB
            file_name="project_proposal.pdf",
            file_path="/uploads/tenant_abc123/project_proposal.pdf",
            media_type="application/pdf",
            file_size_bytes=1048576,  # 1MB
            tag="proposal",
            file_metadata={
                "author": "John Doe",
                "description": "Q4 project proposal",
                "version": 3,
            },
        )
        session.add(file)
        await session.commit()
    logger.debug("File inserted")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
