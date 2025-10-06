from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, status

from fastapi.middleware.cors import CORSMiddleware
from shared.base import Base
from shared.cache import get_redis_client
from shared.db import SessionLocal
import file_service.routes.tenant as tenant_routes
import file_service.routes.files as file_routes
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from shared.config import settings
from shared.db import get_db, engine, SessionLocal

async def get_redis():
    redis = await get_redis_client()
    try:
        yield redis
    finally:
        await redis.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    # Startup code
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    redis_client = aioredis.from_url(
        settings.file_repo_redis_url, decode_responses=True
    )
    await redis_client.ping()

    yield  # app runs here

    # Shutdown code
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(
    title="File Service API",
    description="API for managing tenants and files",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    tenant_routes.router,
    dependencies=[Depends(get_db), Depends(get_redis)],
    tags=["Tenants"],
)

app.include_router(
    file_routes.router,
    dependencies=[Depends(get_db), Depends(get_redis)],
    tags=["Files"],
)


@app.get("/")
async def root() -> dict:
    return {"file_service": "Running"}


@app.get("/ping", status_code=status.HTTP_200_OK)
async def ping() -> str:
    return "PONG"
