from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from src.shared.config import settings
from src.shared.utils import setup_logger
import asyncio
from src.file_service.models import Tenant, File
from src.shared.base import Base

logger = setup_logger()

engine = create_async_engine(url=settings.file_repo_postgresql_url)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
logger.debug("DB engine and Sessionmaker is created")


async def create_db():
    async with engine.begin() as conn:

        await conn.run_sync(Base.metadata.create_all)
        logger.debug("Tables Created")


# We don't need delete here - can be defined in pytest testing scripts
# async def delete_db():
#     async with engine.begin() as conn:
#         from src.file_service.models import Tenant, Base

#         await conn.run_sync(Base.metadata.drop_all)
#         # await conn.run_sync(Base.metadata.create_all)
#         logger.debug("Tables Deleted")


# For VSCode terminal
if __name__ == "__main__":
    asyncio.run(create_db())
