# import sys
# import os

# # Add 'src/' to sys.path if not already there
# SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
# if SRC_DIR not in sys.path:
#     sys.path.insert(0, SRC_DIR)

import json
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from shared.db import SessionLocal
from shared.cache import get_redis_client
from file_service.schemas import TenantCreate, TenantUpdate
from file_service.services import tenant_service


@pytest.mark.anyio
async def test_tenant_crud_flow(monkeypatch):
    # Stub Redis client to avoid real network
    class DummyRedis:
        async def get(self, *a, **k):
            return None
        async def set(self, *a, **k):
            return True
        async def delete(self, *a, **k):
            return True
        async def aclose(self):
            return None

    from src.shared import cache as cache_module
    async def fake_get_redis_client():
        return DummyRedis()
    monkeypatch.setattr(cache_module, "get_redis_client", fake_get_redis_client)

    async with SessionLocal() as db:
        redis = await fake_get_redis_client()

        tenant_code = "T" + uuid.uuid4().hex[:7].upper()
        print(f"\n=== Creating Tenant {tenant_code} ===")

        payload = TenantCreate(
            tenant_code=tenant_code,
            configuration={
                "max_file_size_kbytes": 100,
                "allowed_extensions": [".pdf", ".txt"],
                "forbidden_extensions": [".exe"],
                "allowed_mime_types": ["application/pdf"],
                "forbidden_mime_types": ["image/jpg"],
                "max_zip_depth": 1,
            },
        )

        tenant = await tenant_service.create_tenant(db, redis, payload)
        assert tenant.tenant_code == tenant_code
        print(
            "Created:",
            tenant.tenant_id,
            tenant.tenant_code,
            json.dumps(tenant.configuration),
        )

        print(f"\n=== Fetching Tenant {tenant_code} (DB + cache) ===")
        fetched = await tenant_service.get_tenant_by_code(db, redis, tenant_code)
        # assert fetched["tenant_code"] == tenant_code

        print("Fetched:", fetched)

        print(f"\n=== Updating Tenant {tenant_code} ===")
        update_payload = TenantUpdate(
            configuration={"max_file_size_kbytes": 200, "allowed_extensions": [".csv"]}
        )
        updated = await tenant_service.update_tenant(
            db, redis, tenant_code, update_payload
        )
        assert updated.configuration["max_file_size_kbytes"] == 200
        print(
            "Updated:",
            updated.tenant_id,
            updated.tenant_code,
            json.dumps(updated.configuration),
        )

        print(f"\n=== Deleting Tenant {tenant_code} ===")
        result = await tenant_service.delete_tenant(db, redis, tenant_code)
        # assert result is True
        print("Delete result:", result)

        print(f"\n=== Verifying Deletion of Tenant {tenant_code} ===")
        with pytest.raises(Exception):
            await tenant_service.get_tenant_by_code(db, redis, tenant_code)

        await redis.aclose()
        await db.close()
