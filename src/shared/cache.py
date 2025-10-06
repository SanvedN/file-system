import json
import os
import redis.asyncio as redis
from redis.exceptions import RedisError
from urllib.parse import urlparse
from shared.config import settings

REDIS_URL = settings.file_repo_redis_url

_redis_client: redis.Redis = None


async def init_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            REDIS_URL, decode_responses=True  # Optional: makes string handling easier
        )


async def get_redis_client() -> redis.Redis:
    if _redis_client is None:
        await init_redis()
    return _redis_client


async def cache_set(key: str, value: str, ex: int = None):
    try:
        client = await get_redis_client()
        await client.set(key, value, ex=ex)
    except RedisError as e:
        print(f"Redis SET error: {e}")


async def cache_get(key: str):
    try:
        client = await get_redis_client()
        return await client.get(key)
    except RedisError as e:
        print(f"Redis GET error: {e}")
        return None


async def cache_delete(key: str):
    try:
        client = await get_redis_client()
        await client.delete(key)
    except RedisError as e:
        print(f"Redis DELETE error: {e}")


# FastAPI dependency
async def get_redis():
    return await get_redis_client()


def redis_key_for_tenant(code: str) -> str:
    return f"tenant:cfg:{code}"


async def cache_set_tenant(
    redis: redis.Redis, code: str, cfg: dict, ttl_seconds: int = 3600
) -> None:
    await redis.set(redis_key_for_tenant(code), json.dumps(cfg), ex=ttl_seconds)


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


# -------------------- File Cache Helpers --------------------


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


# -------------------- Embeddings Cache Helpers --------------------


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