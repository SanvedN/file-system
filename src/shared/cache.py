import json
import os
import redis.asyncio as redis
from redis.exceptions import RedisError
from urllib.parse import urlparse
from shared.config import settings
from file_service.models import Tenant

REDIS_URL = settings.file_repo_redis_url

_redis_client: redis.Redis = None


async def init_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            REDIS_URL, 
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )


async def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        await init_redis()
    try:
        # Test connection health
        await _redis_client.ping()
        return _redis_client
    except RedisError:
        # If connection is bad, try to recreate it
        _redis_client = None
        await init_redis()
        return _redis_client


async def cache_set(key: str, value: str, ex: int = None):
    """
    Set cache value with error handling.
    If Redis is down, silently fail (graceful degradation).
    """
    try:
        client = await get_redis_client()
        await client.set(key, value, ex=ex)
    except RedisError as e:
        print(f"Redis SET error (graceful degradation): {e}")
        # Log the specific error type for debugging
        import logging
        logging.warning(f"Redis error writing cache: {type(e).__name__}: {e}")


async def cache_get(key: str):
    """
    Get cache value with error handling.
    If Redis is down, return None (graceful degradation).
    """
    try:
        client = await get_redis_client()
        return await client.get(key)
    except RedisError as e:
        print(f"Redis GET error (graceful degradation): {e}")
        # Log the specific error type for debugging
        import logging
        logging.warning(f"Redis error reading cache: {type(e).__name__}: {e}")
        return None


async def cache_delete(key: str):
    """
    Delete cache value with error handling.
    If Redis is down, silently fail (graceful degradation).
    """
    try:
        client = await get_redis_client()
        await client.delete(key)
    except RedisError as e:
        print(f"Redis DELETE error (graceful degradation): {e}")
        # Log the specific error type for debugging
        import logging
        logging.warning(f"Redis error deleting cache: {type(e).__name__}: {e}")


# FastAPI dependency
async def get_redis():
    return await get_redis_client()


def redis_key_for_tenant(code: str) -> str:
    return f"tenant:cfg:{code}"


async def cache_set_tenant(redis: redis.Redis, code: str, tenant: Tenant, ttl_seconds: int = 3600) -> None:
    cache_data = {
        "tenant_id": str(tenant.tenant_id),
        "tenant_code": tenant.tenant_code,
        "configuration": tenant.configuration or {},
        "created_at": tenant.created_at.isoformat(),
        "updated_at": tenant.updated_at.isoformat()
    }
    await redis.set(redis_key_for_tenant(code), json.dumps(cache_data), ex=ttl_seconds)


async def cache_get_tenant(redis: redis.Redis, code: str) -> dict | None:
    v = await redis.get(redis_key_for_tenant(code))
    if v is None:
        return None
    try:
        return json.loads(v)
    except Exception:
        return None


async def cache_delete_tenant(redis: redis.Redis, code: str) -> None:
    await redis.delete(redis_key_for_tenant(code))

def redis_key_for_files_list(tenant_id: str) -> str:
    return f"files:list:{tenant_id}"


def redis_key_for_file_detail(tenant_id: str, file_id: str) -> str:
    return f"files:detail:{tenant_id}:{file_id}"


async def cache_set_files_list(
    redis: redis.Redis, tenant_id: str, files: list[dict], ttl_seconds: int = 300
) -> None:
    await redis.set(redis_key_for_files_list(tenant_id), json.dumps(files), ex=ttl_seconds)


async def cache_get_files_list(redis: redis.Redis, tenant_id: str) -> list[dict] | None:
    v = await redis.get(redis_key_for_files_list(tenant_id))
    if v is None:
        return None
    try:
        return json.loads(v)
    except Exception:
        return None


async def cache_delete_files_list(redis: redis.Redis, tenant_id: str) -> None:
    await redis.delete(redis_key_for_files_list(tenant_id))


async def cache_set_file_detail(
    redis: redis.Redis, tenant_id: str, file_id: str, file_obj: dict, ttl_seconds: int = 300
) -> None:
    await redis.set(
        redis_key_for_file_detail(tenant_id, file_id), json.dumps(file_obj), ex=ttl_seconds
    )


async def cache_get_file_detail(
    redis: redis.Redis, tenant_id: str, file_id: str
) -> dict | None:
    v = await redis.get(redis_key_for_file_detail(tenant_id, file_id))
    if v is None:
        return None
    try:
        return json.loads(v)
    except Exception:
        return None


async def cache_delete_file_detail(redis: redis.Redis, tenant_id: str, file_id: str) -> None:
    await redis.delete(redis_key_for_file_detail(tenant_id, file_id))



def redis_key_for_emb_pages(file_id: str) -> str:
    return f"emb:pages:{file_id}"


def redis_key_for_emb_search_tenant(tenant_id: str, qhash: str, top_k: int) -> str:
    return f"emb:search:t:{tenant_id}:{qhash}:{top_k}"


def redis_key_for_emb_search_file(file_id: str, qhash: str, top_k: int) -> str:
    return f"emb:search:f:{file_id}:{qhash}:{top_k}"


async def cache_set_emb_pages(redis: redis.Redis, file_id: str, pages: list[dict], ttl_seconds: int = 600) -> None:
    await redis.set(redis_key_for_emb_pages(file_id), json.dumps(pages), ex=ttl_seconds)


async def cache_get_emb_pages(redis: redis.Redis, file_id: str) -> list[dict] | None:
    v = await redis.get(redis_key_for_emb_pages(file_id))
    if not v:
        return None
    try:
        return json.loads(v)
    except Exception:
        return None


async def cache_delete_emb_pages(redis: redis.Redis, file_id: str) -> None:
    await redis.delete(redis_key_for_emb_pages(file_id))


async def cache_set_search(redis: redis.Redis, key: str, rows: list[dict], ttl_seconds: int = 300) -> None:
    await redis.set(key, json.dumps(rows), ex=ttl_seconds)


async def cache_get_search(redis: redis.Redis, key: str) -> list[dict] | None:
    v = await redis.get(key)
    if not v:
        return None
    try:
        return json.loads(v)
    except Exception:
        return None