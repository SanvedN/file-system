import pytest
import asyncio
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.shared.db import Base
from src.file_service.schemas import TenantCreate
from src.file_service.services import tenant_service
from src.file_service.crud.file import FileCRUD
from uuid import uuid4
import os


@pytest.mark.asyncio
async def test_tenant_and_file_crud():
    # Start ephemeral Postgres + Redis
    with (
        PostgresContainer("postgres:15-alpine") as postgres,
        RedisContainer("redis:7-alpine") as redis,
    ):
        db_url = postgres.get_connection_url().replace("psycopg2", "asyncpg")
        # Redis host and port
        redis_host = redis.get_container_host_ip()
        redis_port = redis.get_exposed_port(redis.port)
        redis_url = f"redis://{redis_host}:{redis_port}"

        # Setup DB
        engine = create_async_engine(db_url, future=True)
        async_session = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Get Redis
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(redis_url, decode_responses=True)

        # Run test
        async with async_session() as db:
            tenant_code = "T123456"
            payload = TenantCreate(
                tenant_code=tenant_code,
            )
            created = await tenant_service.create_tenant(db, redis_client, payload)
            assert created.tenant_code == tenant_code

            fetched = await tenant_service.get_tenant_by_code(
                db, redis_client, tenant_code
            )
            assert fetched["tenant_code"] == tenant_code
            print("Fetched: ", fetched)

            await tenant_service.delete_tenant(db, redis_client, tenant_code)
            with pytest.raises(Exception):
                await tenant_service.get_tenant_by_code(db, redis_client, tenant_code)

        # Recreate tenant and test file CRUD on real DB
        async with async_session() as db:
            payload = TenantCreate(tenant_code="TABC123")
            tenant = await tenant_service.create_tenant(db, redis_client, payload)
            tenant_id = tenant.tenant_id

            file_crud = FileCRUD()
            # Create one file row
            file_id = f"CF_FR_{uuid4().hex[:12]}"
            obj = await file_crud.create(
                db,
                tenant_id=tenant_id,
                file_id=file_id,
                file_name="doc.txt",
                file_path=f"/tmp/{file_id}.txt",
                media_type="text/plain",
                file_size_bytes=12,
                tag="invoice",
                file_metadata={"k": "v"},
            )
            assert obj.file_id == file_id

            # List by tenant
            rows = await file_crud.list_by_tenant(db, tenant_id)
            assert any(r.file_id == file_id for r in rows)

            # Get by id
            got = await file_crud.get_by_id(db, tenant_id, file_id)
            assert got is not None and got.file_name == "doc.txt"

            # Search by tag
            items, total = await file_crud.search(
                db,
                tenant_id=tenant_id,
                filters={"tag": "invoice"},
                sort_field="created_at",
                sort_order="desc",
                page=1,
                limit=10,
            )
            assert total >= 1 and any(i.file_id == file_id for i in items)

            # Delete file
            deleted = await file_crud.delete(db, tenant_id=tenant_id, file_id=file_id)
            assert deleted is not None

            # Ensure gone
            got2 = await file_crud.get_by_id(db, tenant_id, file_id)
            assert got2 is None

        await redis_client.aclose()
