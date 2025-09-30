import asyncio
import warnings
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from src.shared.config import settings
from src.shared.utils import setup_logger
from src.file_service.models import Tenant, File
from src.shared.base import Base
import warnings

warnings.simplefilter("always", DeprecationWarning)  # Show all DeprecationWarnings


# Setup logger
logger = setup_logger()

# Database engine setup
engine = create_async_engine(url=settings.file_repo_postgresql_url)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
logger.debug("DB engine and Sessionmaker is created")


# Decorator for deprecation warnings
def deprecated(func):
    async def wrapper(*args, **kwargs):
        warnings.warn(
            f"{func.__name__} is deprecated and will be removed in the future. "
            "Please use Alembic migrations to manage your database schema.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await func(*args, **kwargs)

    return wrapper


# Apply the decorator to the create_db function
@deprecated
async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.debug("Tables Created")


# For VSCode terminal
if __name__ == "__main__":
    asyncio.run(create_db())
